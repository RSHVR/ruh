"""Review Vector Service for semantic search over product reviews.

Uses Cohere for embeddings and reranking, Supabase pgvector for storage.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from .config import settings
from .database import db

if TYPE_CHECKING:
    import cohere

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Clean text before embedding.

    Based on scraper-agent's html_cleaner._clean_text() approach.
    """
    if not text:
        return ""
    # Remove excessive whitespace (newlines, tabs, multiple spaces)
    text = re.sub(r'\s+', ' ', text)
    # Remove repeated punctuation (... → ., !!! → !)
    text = re.sub(r'([.!?,])\1+', r'\1', text)
    # Remove standalone special characters
    text = re.sub(r'\s+[^\w\s]\s+', ' ', text)
    # Remove zero-width characters
    text = text.replace('\u200b', '').replace('\ufeff', '').replace('\u00a0', ' ')
    return text.strip()


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
        """Parse reviews from Amazon HTML into structured data.

        Args:
            html: Raw HTML from Amazon reviews pages

        Returns:
            List of review dicts with text, rating, reviewer, etc.
        """
        reviews = []
        soup = BeautifulSoup(html, 'lxml')

        # Find all review containers
        review_divs = soup.find_all('div', {'data-hook': 'review'})

        for div in review_divs:
            try:
                review = {}

                # Extract review text and clean it
                text_el = div.find('span', {'data-hook': 'review-body'})
                if text_el:
                    raw_text = text_el.get_text(strip=True)
                    review['review_text'] = clean_text(raw_text)
                else:
                    continue  # Skip reviews without text

                # Extract rating (e.g., "4.0 out of 5 stars")
                rating_el = div.find('i', {'data-hook': 'review-star-rating'})
                if not rating_el:
                    rating_el = div.find('i', {'data-hook': 'cmps-review-star-rating'})
                if rating_el:
                    rating_text = rating_el.get_text()
                    rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
                    if rating_match:
                        review['review_rating'] = int(float(rating_match.group(1)))

                # Extract reviewer name
                reviewer_el = div.find('span', class_='a-profile-name')
                if reviewer_el:
                    review['reviewer_name'] = reviewer_el.get_text(strip=True)

                # Extract review date
                date_el = div.find('span', {'data-hook': 'review-date'})
                if date_el:
                    review['review_date'] = date_el.get_text(strip=True)

                # Check if verified purchase
                verified_el = div.find('span', {'data-hook': 'avp-badge'})
                review['verified_purchase'] = verified_el is not None

                # Extract helpful votes
                helpful_el = div.find('span', {'data-hook': 'helpful-vote-statement'})
                if helpful_el:
                    helpful_text = helpful_el.get_text()
                    helpful_match = re.search(r'(\d+)', helpful_text)
                    if helpful_match:
                        review['helpful_votes'] = int(helpful_match.group(1))
                    elif 'one person' in helpful_text.lower():
                        review['helpful_votes'] = 1
                    else:
                        review['helpful_votes'] = 0
                else:
                    review['helpful_votes'] = 0

                reviews.append(review)

            except Exception as e:
                logger.warning(f"Failed to parse review: {e}")
                continue

        logger.info(f"Parsed {len(reviews)} reviews from HTML")
        return reviews

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

        # Parse reviews from HTML
        reviews = self.parse_reviews_html(reviews_html)
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
        if not db.is_available:
            return []

        # Embed query
        query_embedding = self.embed_text(query, input_type="search_query")
        if not query_embedding:
            logger.warning("Failed to embed query")
            return []

        try:
            # Build filter conditions
            # Use Supabase RPC for vector search
            result = db.supabase.rpc(
                'search_reviews',
                {
                    'query_embedding': query_embedding,
                    'match_url_hash': url_hash,
                    'match_threshold': 0.3,
                    'match_count': top_k
                }
            ).execute()

            if not result.data:
                return []

            # Apply additional filters
            candidates = result.data
            if min_rating:
                candidates = [c for c in candidates if c.get('review_rating', 0) >= min_rating]
            if verified_only:
                candidates = [c for c in candidates if c.get('verified_purchase')]

            # Rerank results
            if candidates and len(candidates) > 1:
                documents = [c['review_text'] for c in candidates]
                reranked = self.rerank(query, documents, top_n=rerank_top_n)

                # Map back to original results with rerank scores
                final_results = []
                for r in reranked:
                    candidate = candidates[r['index']]
                    candidate['rerank_score'] = r['score']
                    final_results.append(candidate)
                return final_results

            return candidates[:rerank_top_n]

        except Exception as e:
            logger.error(f"Review search failed: {e}")
            return []

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


# Global service instance
review_vector_service = ReviewVectorService()
