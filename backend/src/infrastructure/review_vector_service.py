"""Review Vector Service for semantic search over product reviews.

Uses Cohere for embeddings and reranking, Supabase pgvector for storage.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from datetime import datetime, timezone

from .config import settings
from .database import db
from .rank_fusion import reciprocal_rank_fusion
from .scrapers.factory import ScraperFactory
from .scrapers.review_parsers import AmazonReviewParser, JsonLdReviewParser

if TYPE_CHECKING:
    import cohere

logger = logging.getLogger(__name__)

# Health-focused search queries for finding relevant reviews
HEALTH_QUERIES = [
    "allergic reaction skin rash irritation burning",
    "headache nausea dizziness sick feeling unwell",
    "breathing problems respiratory issues coughing",
    "chemical smell toxic fumes strong odor",
    "burn injury hurt dangerous unsafe",
]


class ReviewVectorService:
    """Service for storing and searching product reviews with vector embeddings.

    Uses:
    - Cohere embed-v4.0 for 1536-dimensional embeddings
    - Cohere rerank-v4.0-fast for result reranking
    - Supabase pgvector for vector storage and similarity search
    """

    def __init__(self):
        """Initialize the review vector service."""
        self.co: Optional[cohere.Client] = None
        self.embed_model = "embed-v4.0"
        self.rerank_model = "rerank-v4.0-fast"
        self.dimensions = 1536

        # Embedding cache to avoid redundant API calls
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_max_size = 1000

        # Resolves the per-retailer review parser by product URL (open/closed).
        self._scraper_factory = ScraperFactory()

    def _init_cohere(self):
        """Initialize Cohere client lazily."""
        if self.co is None:
            if not settings.cohere_api_key:
                logger.warning("Cohere API key not configured - embeddings disabled")
                return False
            import cohere
            self.co = cohere.Client(settings.cohere_api_key)
            logger.info("Cohere client initialized")
        return True

    def _get_cache_key(self, text: str, input_type: str) -> str:
        """Generate cache key for embedding."""
        # Use first 100 chars + length as cache key (faster than hashing full text)
        return f"{input_type}:{len(text)}:{text[:100]}"

    def _get_cached_embedding(self, text: str, input_type: str) -> Optional[List[float]]:
        """Get cached embedding if available."""
        cache_key = self._get_cache_key(text, input_type)
        return self._embedding_cache.get(cache_key)

    def _cache_embedding(self, text: str, embedding: List[float], input_type: str):
        """Cache embedding for future use."""
        if len(self._embedding_cache) >= self._cache_max_size:
            # Remove oldest entry (FIFO)
            oldest_key = next(iter(self._embedding_cache))
            del self._embedding_cache[oldest_key]
        cache_key = self._get_cache_key(text, input_type)
        self._embedding_cache[cache_key] = embedding

    def embed_text(self, text: str, input_type: str = "search_document") -> Optional[List[float]]:
        """Embed text using Cohere API with caching.

        Args:
            text: Text to embed
            input_type: "search_document" for indexing, "search_query" for queries

        Returns:
            1536-dimensional embedding vector, or None if failed
        """
        if not self._init_cohere():
            return None

        # Check cache first
        cached = self._get_cached_embedding(text, input_type)
        if cached is not None:
            return cached

        try:
            response = self.co.embed(
                texts=[text],
                model=self.embed_model,
                input_type=input_type,
                embedding_types=["float"],
                truncate="END"  # Truncate long texts from end
            )
            embedding = list(response.embeddings.float_[0])
            self._cache_embedding(text, embedding, input_type)
            return embedding

        except Exception as e:
            logger.error(f"Cohere embed failed: {e}")
            return None

    def embed_batch(self, texts: List[str], input_type: str = "search_document") -> List[Optional[List[float]]]:
        """Embed multiple texts in batch (max 96 per batch).

        Args:
            texts: List of texts to embed
            input_type: "search_document" for indexing, "search_query" for queries

        Returns:
            List of embeddings (None for failed items)
        """
        if not self._init_cohere():
            return [None] * len(texts)

        all_embeddings: List[Optional[List[float]]] = []
        batch_size = 96  # Cohere limit

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Check cache for each item
            batch_embeddings: List[Optional[List[float]]] = []
            texts_to_embed: List[str] = []
            embed_indices: List[int] = []

            for j, text in enumerate(batch):
                cached = self._get_cached_embedding(text, input_type)
                if cached is not None:
                    batch_embeddings.append(cached)
                else:
                    batch_embeddings.append(None)
                    texts_to_embed.append(text)
                    embed_indices.append(j)

            # Embed uncached texts
            if texts_to_embed:
                try:
                    response = self.co.embed(
                        texts=texts_to_embed,
                        model=self.embed_model,
                        input_type=input_type,
                        embedding_types=["float"],
                        truncate="END"
                    )

                    for idx, embedding in zip(embed_indices, response.embeddings.float_):
                        emb_list = list(embedding)
                        batch_embeddings[idx] = emb_list
                        self._cache_embedding(batch[idx], emb_list, input_type)

                except Exception as e:
                    logger.error(f"Cohere batch embed failed: {e}")

            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def rerank(self, query: str, documents: List[str], top_n: int = 10) -> List[Dict[str, Any]]:
        """Rerank documents by relevance using Cohere.

        Args:
            query: Search query
            documents: List of document texts
            top_n: Number of top results to return

        Returns:
            List of {index, text, score} dicts sorted by relevance
        """
        if not self._init_cohere() or not documents:
            return []

        try:
            response = self.co.rerank(
                query=query,
                documents=documents,
                model=self.rerank_model,
                top_n=min(top_n, len(documents)),
                return_documents=True
            )

            results = []
            for r in response.results:
                results.append({
                    "index": r.index,
                    "text": r.document.text,
                    "score": r.relevance_score
                })
            return results

        except Exception as e:
            logger.error(f"Cohere rerank failed: {e}")
            return []

    def parse_reviews_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse Amazon reviews HTML into structured dicts (backward-compatible shim).

        Retailer-agnostic parsing goes through :meth:`parse_reviews_for_url`, which
        resolves the retailer's own parser. This method is kept for the Amazon DOM
        so existing callers keep working; it accepts both the renamed 2026 hooks and
        the legacy ones (see AmazonReviewParser).
        """
        return AmazonReviewParser().parse(html)

    async def parse_reviews_for_url(
        self, product_url: str, reviews_html: str
    ) -> List[Dict[str, Any]]:
        """Parse reviews using the retailer-appropriate parser for ``product_url``.

        The review-DOM dialect lives WITH the retailer (its scraper's
        ``REVIEW_PARSER``); URLs with no registered scraper fall back to the generic
        schema.org JSON-LD parser. Never raises (INV-3) — any failure yields ``[]``.
        """
        if not reviews_html:
            return []

        scraper = None
        try:
            scraper = await self._scraper_factory.get_scraper(product_url)
        except Exception as e:
            logger.warning(f"Scraper resolution failed for reviews ({product_url}): {e}")

        try:
            if scraper is not None:
                return scraper.parse_reviews(reviews_html)
            return JsonLdReviewParser().parse(reviews_html)
        except Exception as e:
            logger.warning(f"Review parsing failed for {product_url}: {e}")
            return []

    async def store_reviews(
        self,
        url_hash: str,
        product_url: str,
        reviews_html: str,
        source: str = "client",
        pages_fetched: int = 1
    ) -> Tuple[int, int]:
        """Parse, embed, and store reviews in Supabase.

        Args:
            url_hash: Product URL hash (links to product_analyses)
            product_url: Original product URL
            reviews_html: Raw HTML containing reviews
            source: "client" or "scraper"
            pages_fetched: Number of pages fetched

        Returns:
            Tuple of (reviews_stored, reviews_failed)
        """
        if not db.is_available:
            logger.warning("Database not available - skipping review storage")
            return 0, 0

        # Parse reviews using the retailer-appropriate parser (Amazon DOM,
        # Walmart __NEXT_DATA__, generic JSON-LD, …) resolved from the URL.
        reviews = await self.parse_reviews_for_url(product_url, reviews_html)
        if not reviews:
            logger.info("No reviews parsed from HTML")
            return 0, 0

        logger.info(f"Storing {len(reviews)} reviews for {url_hash[:16]}...")

        # Extract review texts for batch embedding
        review_texts = [r.get('review_text', '') for r in reviews]

        # Batch embed all reviews
        embeddings = self.embed_batch(review_texts, input_type="search_document")

        # Store each review with its embedding
        stored = 0
        failed = 0
        rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for i, (review, embedding) in enumerate(zip(reviews, embeddings)):
            try:
                # Track rating distribution
                rating = review.get('review_rating')
                if rating and 1 <= rating <= 5:
                    rating_counts[rating] += 1

                # Prepare data for Supabase
                chunk_data = {
                    'url_hash': url_hash,
                    'product_url': product_url,
                    'review_text': review.get('review_text', '')[:10000],  # Limit text length
                    'review_rating': rating,
                    'reviewer_name': review.get('reviewer_name'),
                    'review_date': review.get('review_date'),
                    'verified_purchase': review.get('verified_purchase', False),
                    'helpful_votes': review.get('helpful_votes', 0),
                    'chunk_index': i,
                    'source': source,
                    'page_number': (i // 10) + 1,  # Approximate page number
                    'fetched_at': datetime.now(timezone.utc).isoformat(),
                }

                # Add embedding if available
                if embedding:
                    chunk_data['embedding'] = embedding

                # Insert into Supabase
                result = db.supabase.table('review_chunks').insert(chunk_data).execute()

                if result.data:
                    stored += 1
                else:
                    failed += 1

            except Exception as e:
                logger.warning(f"Failed to store review {i}: {e}")
                failed += 1

        # Update or create review summary
        try:
            total_reviews = sum(rating_counts.values())
            verified_count = sum(1 for r in reviews if r.get('verified_purchase'))
            avg_rating = sum(r * c for r, c in rating_counts.items()) / max(total_reviews, 1)

            summary_data = {
                'url_hash': url_hash,
                'product_url': product_url,
                'total_reviews': total_reviews,
                'pages_fetched': pages_fetched,
                'rating_5_count': rating_counts[5],
                'rating_4_count': rating_counts[4],
                'rating_3_count': rating_counts[3],
                'rating_2_count': rating_counts[2],
                'rating_1_count': rating_counts[1],
                'verified_ratio': verified_count / max(total_reviews, 1),
                'avg_rating': round(avg_rating, 2),
                'source': source,
                'fetched_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }

            db.supabase.table('review_summaries').upsert(
                summary_data,
                on_conflict='url_hash'
            ).execute()

        except Exception as e:
            logger.warning(f"Failed to update review summary: {e}")

        logger.info(f"✅ Stored {stored} reviews, {failed} failed")
        return stored, failed

    async def search_reviews(
        self,
        query: str,
        url_hash: Optional[str] = None,
        top_k: int = 30,
        rerank_top_n: int = 10,
        min_rating: Optional[int] = None,
        verified_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Search reviews by semantic similarity with optional reranking.

        Args:
            query: Search query (e.g., "skin irritation", "allergic reaction")
            url_hash: Filter to specific product (optional)
            top_k: Number of candidates to retrieve
            rerank_top_n: Number of results after reranking
            min_rating: Filter by minimum rating (optional)
            verified_only: Only include verified purchases

        Returns:
            List of relevant review chunks with similarity scores
        """
        candidates = self._semantic_candidates(
            query, url_hash, top_k, min_rating=min_rating, verified_only=verified_only
        )
        if not candidates:
            return []
        return self._rerank_candidates(query, candidates, rerank_top_n)

    def _semantic_candidates(
        self,
        query: str,
        url_hash: Optional[str],
        top_k: int,
        min_rating: Optional[int] = None,
        verified_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Semantic/pgvector candidates (embed + search_reviews RPC), no rerank.

        Returns [] on any failure (missing embedding, RPC error) so the caller can
        degrade to lexical-only (INV-3).
        """
        if not db.is_available:
            return []

        query_embedding = self.embed_text(query, input_type="search_query")
        if not query_embedding:
            logger.warning("Failed to embed query - semantic search unavailable")
            return []

        try:
            result = db.supabase.rpc(
                'search_reviews',
                {
                    'query_embedding': query_embedding,
                    'match_url_hash': url_hash,
                    'match_threshold': 0.3,
                    'match_count': top_k,
                },
            ).execute()
        except Exception as e:
            logger.error(f"Semantic review search failed: {e}")
            return []

        return self._apply_filters(result.data or [], min_rating, verified_only)

    def _lexical_candidates(
        self,
        query: str,
        url_hash: Optional[str],
        top_k: int,
        min_rating: Optional[int] = None,
        verified_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Lexical/full-text candidates via search_reviews_lexical RPC (migration 019).

        Needs no embedding, so it works even when Cohere is unavailable — this is
        what guarantees exact term matches ("PFOA", "rash") are never missed.
        Returns [] on failure so the caller degrades to semantic-only (INV-3).
        """
        if not db.is_available:
            return []

        try:
            result = db.supabase.rpc(
                'search_reviews_lexical',
                {
                    'p_query': query,
                    'p_url_hash': url_hash,
                    'p_limit': top_k,
                },
            ).execute()
        except Exception as e:
            logger.warning(f"Lexical review search failed: {e}")
            return []

        return self._apply_filters(result.data or [], min_rating, verified_only)

    @staticmethod
    def _apply_filters(
        candidates: List[Dict[str, Any]],
        min_rating: Optional[int],
        verified_only: bool,
    ) -> List[Dict[str, Any]]:
        """Apply the optional rating / verified-purchase filters to a candidate list."""
        if min_rating:
            candidates = [c for c in candidates if (c.get('review_rating') or 0) >= min_rating]
        if verified_only:
            candidates = [c for c in candidates if c.get('verified_purchase')]
        return candidates

    def _rerank_candidates(
        self, query: str, candidates: List[Dict[str, Any]], top_n: int
    ) -> List[Dict[str, Any]]:
        """Cohere-rerank a candidate pool, returning enriched copies (adds rerank_score).

        Falls back to the incoming order (e.g. RRF-fused order) when rerank is
        unavailable, so a reranker outage never drops results (INV-3).
        """
        if not candidates:
            return []
        if len(candidates) == 1:
            return [dict(candidates[0])]

        documents = [c.get('review_text', '') for c in candidates]
        reranked = self.rerank(query, documents, top_n=top_n)
        if not reranked:
            return [dict(c) for c in candidates[:top_n]]

        final_results: List[Dict[str, Any]] = []
        for r in reranked:
            candidate = dict(candidates[r['index']])
            candidate['rerank_score'] = r['score']
            final_results.append(candidate)
        return final_results

    async def get_review_summary(self, url_hash: str) -> Optional[Dict[str, Any]]:
        """Get review summary for a product.

        Args:
            url_hash: Product URL hash

        Returns:
            Review summary dict or None
        """
        if not db.is_available:
            return None

        try:
            result = db.supabase.table('review_summaries').select('*').eq(
                'url_hash', url_hash
            ).execute()

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"Failed to get review summary: {e}")
            return None

    async def get_health_relevant_reviews(
        self,
        url_hash: str,
        max_reviews: int = 15
    ) -> List[Dict[str, Any]]:
        """Get reviews most likely to contain health concerns.

        HYBRID retrieval: for each health-focused query we run BOTH the semantic
        (pgvector) and lexical (full-text, migration 019) retrievers, fuse their
        rankings with Reciprocal Rank Fusion, then Cohere-rerank the fused pool as
        the final stage before cutting to ``max_reviews``. Adding lexical retrieval
        guarantees exact term hits (substance names like "PFOA"/"benzene", symptoms
        like "rash"/"hives") are never missed just because an embedding ranked them
        low. Each retriever degrades independently (INV-3): lexical failure →
        semantic-only, semantic/Cohere failure → lexical-only.

        Args:
            url_hash: Product URL hash
            max_reviews: Maximum number of reviews to return

        Returns:
            List of health-relevant review dicts sorted by relevance (shape
            unchanged from the semantic-only version — callers need no changes).
        """
        if not db.is_available:
            return []

        all_results: List[Dict[str, Any]] = []
        seen_texts: set = set()

        logger.info(
            f"🔍 Hybrid (semantic + lexical) search for health-relevant reviews "
            f"across {len(HEALTH_QUERIES)} queries..."
        )

        for query in HEALTH_QUERIES:
            try:
                # semantic top-K ∪ lexical top-K → RRF order → rerank → collect
                semantic = self._semantic_candidates(query, url_hash, top_k=10)
                lexical = self._lexical_candidates(query, url_hash, top_k=10)
                fused = reciprocal_rank_fusion([semantic, lexical])
                if not fused:
                    continue

                for r in self._rerank_candidates(query, fused, top_n=5):
                    # Deduplicate by first 100 chars of review text
                    text_key = r.get('review_text', '')[:100]
                    if text_key and text_key not in seen_texts:
                        seen_texts.add(text_key)
                        all_results.append(r)

            except Exception as e:
                logger.warning(f"Hybrid search failed for query '{query[:30]}...': {e}")
                continue

        # Sort by best available relevance signal: rerank score, then RRF, then similarity.
        all_results.sort(
            key=lambda x: x.get('rerank_score', x.get('rrf_score', x.get('similarity', 0))),
            reverse=True,
        )

        final_results = all_results[:max_reviews]
        logger.info(f"✅ Found {len(final_results)} health-relevant reviews (from {len(seen_texts)} unique matches)")

        return final_results


# Global service instance
review_vector_service = ReviewVectorService()
