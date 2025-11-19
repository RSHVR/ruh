"""Supabase database service layer."""

import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from supabase import create_client, Client

from .config import settings

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for interacting with Supabase database."""

    def __init__(self):
        """Initialize Supabase client."""
        self.client: Optional[Client] = None
        self._anonymous_user_id: Optional[UUID] = None

        if settings.supabase_url and settings.supabase_key:
            try:
                self.client = create_client(
                    settings.supabase_url,
                    settings.supabase_key
                )
                logger.info("Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                self.client = None
        else:
            logger.warning("Supabase credentials not configured, database features disabled")

    @property
    def is_available(self) -> bool:
        """Check if database is available."""
        return self.client is not None

    async def get_or_create_anonymous_user(self) -> UUID:
        """Get or create a default anonymous user for tracking searches.

        Returns:
            UUID: The anonymous user ID
        """
        if self._anonymous_user_id:
            return self._anonymous_user_id

        if not self.is_available:
            # Return a static UUID if database is not available
            return UUID('00000000-0000-0000-0000-000000000000')

        try:
            # Check if anonymous user exists
            response = self.client.table('users').select('id').eq('id', '00000000-0000-0000-0000-000000000000').execute()

            if response.data:
                self._anonymous_user_id = UUID(response.data[0]['id'])
            else:
                # Create anonymous user
                user_data = {
                    'id': '00000000-0000-0000-0000-000000000000',
                    'created_at': datetime.utcnow().isoformat()
                }
                response = self.client.table('users').insert(user_data).execute()
                self._anonymous_user_id = UUID(response.data[0]['id'])

            return self._anonymous_user_id
        except Exception as e:
            logger.error(f"Failed to get/create anonymous user: {e}")
            return UUID('00000000-0000-0000-0000-000000000000')

    def generate_url_hash(self, url: str) -> str:
        """Generate SHA256 hash of product URL for efficient lookups.

        Args:
            url: Product URL

        Returns:
            Hex string of SHA256 hash
        """
        return hashlib.sha256(url.encode()).hexdigest()

    async def get_cached_analysis(self, url_hash: str) -> Optional[Dict[str, Any]]:
        """Check if product analysis exists in cache.

        Args:
            url_hash: SHA256 hash of product URL

        Returns:
            Cached analysis data or None if not found
        """
        if not self.is_available:
            return None

        try:
            response = self.client.table('product_analyses')\
                .select('*')\
                .eq('product_url_hash', url_hash)\
                .execute()

            if response.data:
                logger.info(f"Cache HIT for URL hash: {url_hash[:16]}...")
                return response.data[0]
            else:
                logger.info(f"Cache MISS for URL hash: {url_hash[:16]}...")
                return None
        except Exception as e:
            logger.error(f"Failed to check cache: {e}")
            return None

    async def store_analysis(
        self,
        url_hash: str,
        product_url: str,
        analysis_data: Dict[str, Any]
    ) -> bool:
        """Store product analysis in database.

        Args:
            url_hash: SHA256 hash of product URL
            product_url: Original product URL
            analysis_data: Analysis response from Claude

        Returns:
            True if stored successfully, False otherwise
        """
        if not self.is_available:
            logger.warning("Database not available, skipping analysis storage")
            return False

        try:
            # Extract data from Claude's response
            analysis = analysis_data.get('analysis', {})

            # Calculate harm score (inverse of safety score)
            harm_score = 100 - analysis.get('overall_score', 0)

            # Prepare data for insertion - match actual schema columns
            ingredients = analysis.get('ingredients', [])
            # Ensure ingredients is a list of strings for PostgreSQL TEXT[] type
            if not isinstance(ingredients, list):
                ingredients = []

            # Get allergens and PFAS - ensure they're lists
            allergens = analysis.get('allergens', analysis.get('allergens_detected', []))
            if not isinstance(allergens, list):
                allergens = []

            pfas = analysis.get('pfas_compounds', analysis.get('pfas_detected', []))
            if not isinstance(pfas, list):
                pfas = []

            other_concerns = analysis.get('other_concerns', [])
            if not isinstance(other_concerns, list):
                other_concerns = []

            db_data = {
                'product_url_hash': url_hash,
                'product_url': product_url,
                'product_name': analysis.get('product_name', ''),
                'brand': analysis.get('brand', ''),
                'category': analysis.get('category', ''),
                'retailer': analysis.get('retailer', ''),
                'ingredients': ingredients,  # PostgreSQL TEXT[] array
                'harm_score': harm_score,
                'overall_score': analysis.get('overall_score', 0),
                'allergens_detected': allergens,  # JSONB - maps to allergens_detected column
                'pfas_detected': pfas,  # JSONB - maps to pfas_detected column
                'other_concerns': other_concerns,  # JSONB
                'confidence': int(analysis.get('confidence', 0.8) * 100),  # INTEGER 0-100
                'analyzed_at': datetime.utcnow().isoformat()
            }

            logger.info(f"About to store analysis with keys: {list(db_data.keys())}")

            # Upsert (insert or update if exists)
            response = self.client.table('product_analyses')\
                .upsert(db_data, on_conflict='product_url_hash')\
                .execute()

            logger.info(f"✅ Stored analysis for: {analysis.get('product_name', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to store analysis: {e}")
            try:
                logger.error(f"Keys being sent: {list(db_data.keys())}")
                logger.error(f"Sample data - product_name: {db_data.get('product_name')}, allergens: {len(db_data.get('allergens_detected', []))} items")
            except:
                logger.error("Could not log db_data details")
            return False

    async def log_search(self, user_id: UUID, product_url: str) -> bool:
        """Log user search in database.

        Args:
            user_id: User ID
            product_url: Product URL searched

        Returns:
            True if logged successfully, False otherwise
        """
        if not self.is_available:
            return False

        try:
            search_data = {
                'user_id': str(user_id),
                'product_url': product_url,
                'searched_at': datetime.utcnow().isoformat()
            }

            self.client.table('user_searches').insert(search_data).execute()
            logger.debug(f"Logged search for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to log search: {e}")
            return False

    async def search_allergens(self, search_term: str) -> List[Dict[str, Any]]:
        """Search allergen knowledge base.

        Args:
            search_term: Allergen name or alias to search

        Returns:
            List of matching allergen records
        """
        if not self.is_available:
            return []

        try:
            # Use the search_allergen SQL function we created in migrations
            response = self.client.rpc('search_allergen', {'search_term': search_term}).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to search allergens: {e}")
            return []

    async def search_pfas(self, search_term: str) -> List[Dict[str, Any]]:
        """Search PFAS knowledge base.

        Args:
            search_term: PFAS compound name or alias to search

        Returns:
            List of matching PFAS records
        """
        if not self.is_available:
            return []

        try:
            # Use the search_pfas SQL function we created in migrations
            response = self.client.rpc('search_pfas', {'search_term': search_term}).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to search PFAS: {e}")
            return []

    async def get_all_allergens(self) -> List[Dict[str, Any]]:
        """Get all allergens from knowledge base.

        Returns:
            List of all allergen records
        """
        if not self.is_available:
            return []

        try:
            response = self.client.table('allergens').select('*').execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get allergens: {e}")
            return []

    async def get_all_pfas(self) -> List[Dict[str, Any]]:
        """Get all PFAS compounds from knowledge base.

        Returns:
            List of all PFAS records
        """
        if not self.is_available:
            return []

        try:
            response = self.client.table('pfas_compounds').select('*').execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get PFAS compounds: {e}")
            return []

    async def cache_review_insights(
        self,
        url_hash: str,
        insights_data: Dict[str, Any]
    ) -> bool:
        """Cache review insights in product_analyses table.

        Args:
            url_hash: Product URL hash
            insights_data: Review insights dictionary

        Returns:
            True if cached successfully
        """
        if not self.is_available:
            logger.debug("Supabase not available - skipping reviews cache")
            return False

        try:
            # Update the product_analyses row with review insights
            response = self.client.table('product_analyses')\
                .update({'review_insights': insights_data})\
                .eq('product_url_hash', url_hash)\
                .execute()

            if response.data:
                logger.debug("✅ Cached review insights")
                return True
            else:
                logger.warning("⚠️  No matching product found to cache reviews")
                return False
        except Exception as e:
            logger.warning(f"⚠️  Failed to cache reviews (non-fatal): {e}")
            return False

    async def get_cached_reviews(self, url_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached review insights from product_analyses table.

        Args:
            url_hash: Product URL hash

        Returns:
            Cached insights if found and fresh (< 7 days), None otherwise
        """
        if not self.is_available:
            return None

        try:
            response = self.client.table('product_analyses')\
                .select('review_insights, analyzed_at')\
                .eq('product_url_hash', url_hash)\
                .execute()

            if response.data and response.data[0].get('review_insights'):
                cached = response.data[0]
                review_insights = cached['review_insights']

                # Check if reviews are populated (not empty dict)
                if not review_insights or review_insights == {}:
                    return None

                # Check freshness (reviews change, cache for 7 days)
                analyzed_at = datetime.fromisoformat(cached['analyzed_at'].replace('Z', '+00:00'))
                age_days = (datetime.utcnow() - analyzed_at).days

                if age_days < 7:
                    return review_insights

            return None
        except Exception as e:
            logger.warning(f"⚠️  Failed to retrieve cached reviews: {e}")
            return None


# Global database service instance
db = DatabaseService()
