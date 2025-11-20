"""Admin API endpoints for monitoring and management."""

from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import logging

from ...infrastructure.database import db
from ..auth import verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/validation-logs")
async def get_validation_logs(
    start_date: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    product_url: Optional[str] = Query(None, description="Filter by product URL"),
    log_type: Optional[str] = Query(None, description="Filter by log type (invalid_allergen, invalid_pfas, etc.)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    api_key: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    """Get validation logs with optional filtering.

    Query Parameters:
        - start_date: Filter logs from this date (ISO format)
        - end_date: Filter logs until this date (ISO format)
        - product_url: Filter by specific product URL
        - log_type: Filter by log type
        - limit: Maximum number of results (default: 100, max: 1000)
        - offset: Pagination offset (default: 0)

    Returns:
        Dictionary with logs array and metadata
    """
    if not db.is_available:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable"
        )

    try:
        # Build query
        query = db.client.table('validation_logs').select('*')

        # Apply filters
        if start_date:
            query = query.gte('timestamp', start_date)

        if end_date:
            query = query.lte('timestamp', end_date)

        if product_url:
            query = query.eq('product_url', product_url)

        if log_type:
            query = query.eq('log_type', log_type)

        # Apply pagination and sorting
        query = query.order('timestamp', desc=True).range(offset, offset + limit - 1)

        # Execute query
        response = query.execute()

        return {
            "logs": response.data,
            "count": len(response.data),
            "offset": offset,
            "limit": limit,
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "product_url": product_url,
                "log_type": log_type
            }
        }

    except Exception as e:
        logger.error(f"Failed to fetch validation logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch validation logs: {str(e)}"
        )


@router.get("/validation-stats")
async def get_validation_stats(
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    api_key: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    """Get validation statistics for the past N days.

    Uses the get_recent_validation_summary SQL function.

    Query Parameters:
        - days: Number of days to look back (default: 7, max: 90)

    Returns:
        Dictionary with validation statistics
    """
    if not db.is_available:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable"
        )

    try:
        # Call SQL function
        response = db.client.rpc('get_recent_validation_summary', {'days_back': days}).execute()

        if not response.data or len(response.data) == 0:
            return {
                "total_products_analyzed": 0,
                "total_invalid_allergens": 0,
                "total_invalid_pfas": 0,
                "accuracy_rate": 100.0,
                "most_problematic_products": [],
                "days_analyzed": days
            }

        stats = response.data[0]
        stats["days_analyzed"] = days

        return stats

    except Exception as e:
        logger.error(f"Failed to fetch validation stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch validation stats: {str(e)}"
        )


@router.get("/flagged-substances")
async def get_flagged_substances(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of substances to return"),
    api_key: str = Depends(verify_api_key)
) -> List[Dict[str, Any]]:
    """Get the most frequently flagged (misclassified) substances.

    Uses the get_most_flagged_substances SQL function.

    Query Parameters:
        - limit: Maximum number of results (default: 20, max: 100)

    Returns:
        List of substances with flagging statistics
    """
    if not db.is_available:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable"
        )

    try:
        # Call SQL function
        response = db.client.rpc('get_most_flagged_substances', {'result_limit': limit}).execute()

        return response.data or []

    except Exception as e:
        logger.error(f"Failed to fetch flagged substances: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch flagged substances: {str(e)}"
        )


@router.get("/stats-by-date")
async def get_stats_by_date(
    start_date: str = Query(..., description="Start date (ISO format: YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (ISO format: YYYY-MM-DD)"),
    api_key: str = Depends(verify_api_key)
) -> List[Dict[str, Any]]:
    """Get daily validation statistics for a date range.

    Uses the get_validation_stats_by_date SQL function.

    Query Parameters:
        - start_date: Start date (required, ISO format)
        - end_date: End date (required, ISO format)

    Returns:
        List of daily statistics
    """
    if not db.is_available:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable"
        )

    try:
        # Parse dates to ensure valid format
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)

        # Call SQL function
        response = db.client.rpc('get_validation_stats_by_date', {
            'start_date': start_dt.isoformat(),
            'end_date': end_dt.isoformat()
        }).execute()

        return response.data or []

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Use ISO format (YYYY-MM-DD): {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to fetch stats by date: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch stats by date: {str(e)}"
        )


@router.get("/product-logs/{product_url:path}")
async def get_product_validation_logs(
    product_url: str,
    api_key: str = Depends(verify_api_key)
) -> List[Dict[str, Any]]:
    """Get all validation logs for a specific product.

    Uses the get_validation_logs_by_product SQL function.

    Path Parameters:
        - product_url: Full product URL (URL-encoded)

    Returns:
        List of validation logs for the product (log_timestamp renamed from timestamp)
    """
    if not db.is_available:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable"
        )

    try:
        # Call SQL function
        response = db.client.rpc('get_validation_logs_by_product', {
            'search_product_url': product_url
        }).execute()

        return response.data or []

    except Exception as e:
        logger.error(f"Failed to fetch product validation logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch product validation logs: {str(e)}"
        )
