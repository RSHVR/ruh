"""Validation logger for tracking Claude AI misclassifications."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ValidationLogger:
    """Logs validation failures when Claude misclassifies substances to Supabase."""

    def __init__(self):
        """Initialize validation logger with Supabase database connection."""
        # Import here to avoid circular dependency
        from .database import db
        self.db = db

    def log_invalid_allergen(
        self,
        substance_name: str,
        severity: str,
        confidence: float,
        source: str,
        product_url: str,
        product_name: str
    ) -> None:
        """Log an allergen that Claude classified but is not in database.

        Args:
            substance_name: Name of substance Claude flagged
            severity: Severity level Claude assigned
            confidence: Confidence score Claude assigned
            source: Where Claude found this (e.g., "ingredient list")
            product_url: Product being analyzed
            product_name: Product name
        """
        log_data = {
            "log_type": "invalid_allergen",
            "product_url": product_url,
            "product_name": product_name,
            "substance_name": substance_name,
            "severity": severity,
            "confidence": float(confidence),
            "source": source,
            "details": {
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

        self._write_to_db(log_data)
        logger.warning(
            f"⚠️  Invalid allergen detected: '{substance_name}' "
            f"(severity={severity}, confidence={confidence:.2f}) in {product_name}"
        )

    def log_invalid_pfas(
        self,
        substance_name: str,
        cas_number: Optional[str],
        confidence: float,
        source: str,
        product_url: str,
        product_name: str
    ) -> None:
        """Log a PFAS compound that Claude classified but is not in database.

        Args:
            substance_name: Name of PFAS Claude flagged
            cas_number: CAS number if provided
            confidence: Confidence score Claude assigned
            source: Where Claude found this
            product_url: Product being analyzed
            product_name: Product name
        """
        log_data = {
            "log_type": "invalid_pfas",
            "product_url": product_url,
            "product_name": product_name,
            "substance_name": substance_name,
            "cas_number": cas_number,
            "confidence": float(confidence),
            "source": source,
            "details": {
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

        self._write_to_db(log_data)
        logger.warning(
            f"⚠️  Invalid PFAS detected: '{substance_name}' "
            f"(CAS={cas_number}, confidence={confidence:.2f}) in {product_name}"
        )

    def log_moved_to_other_concerns(
        self,
        substance_name: str,
        original_category: str,
        new_category: str,
        reason: str,
        product_url: str,
        product_name: str
    ) -> None:
        """Log when a substance is moved from allergens/PFAS to other_concerns.

        Args:
            substance_name: Name of substance
            original_category: Where Claude put it ("allergen" or "pfas")
            new_category: New category assigned
            reason: Reason for reclassification
            product_url: Product being analyzed
            product_name: Product name
        """
        log_data = {
            "log_type": "reclassified_substance",
            "product_url": product_url,
            "product_name": product_name,
            "substance_name": substance_name,
            "category": new_category,
            "details": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "original_category": original_category,
                "new_category": new_category,
                "reason": reason
            }
        }

        self._write_to_db(log_data)
        logger.info(
            f"ℹ️  Reclassified: '{substance_name}' "
            f"from {original_category} to {new_category} ({reason})"
        )

    def log_validation_summary(
        self,
        product_name: str,
        product_url: str,
        allergens_total: int,
        allergens_valid: int,
        allergens_invalid: int,
        pfas_total: int,
        pfas_valid: int,
        pfas_invalid: int
    ) -> None:
        """Log summary of validation for a product analysis.

        Args:
            product_name: Product name
            product_url: Product URL
            allergens_total: Total allergens Claude detected
            allergens_valid: Valid allergens (in database)
            allergens_invalid: Invalid allergens (not in database)
            pfas_total: Total PFAS Claude detected
            pfas_valid: Valid PFAS (in database)
            pfas_invalid: Invalid PFAS (not in database)
        """
        log_data = {
            "log_type": "validation_summary",
            "product_url": product_url,
            "product_name": product_name,
            "details": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "allergens": {
                    "total": allergens_total,
                    "valid": allergens_valid,
                    "invalid": allergens_invalid,
                    "accuracy": (allergens_valid / allergens_total * 100) if allergens_total > 0 else 100.0
                },
                "pfas": {
                    "total": pfas_total,
                    "valid": pfas_valid,
                    "invalid": pfas_invalid,
                    "accuracy": (pfas_valid / pfas_total * 100) if pfas_total > 0 else 100.0
                }
            }
        }

        self._write_to_db(log_data)

        if allergens_invalid > 0 or pfas_invalid > 0:
            logger.warning(
                f"📊 Validation summary for {product_name}: "
                f"Allergens {allergens_valid}/{allergens_total} valid, "
                f"PFAS {pfas_valid}/{pfas_total} valid"
            )
        else:
            logger.info(
                f"✅ All substances validated for {product_name}: "
                f"{allergens_valid} allergens, {pfas_valid} PFAS"
            )

    def _write_to_db(self, log_data: Dict[str, Any]) -> None:
        """Write log entry to Supabase database.

        Args:
            log_data: Dictionary with log data matching validation_logs table schema
        """
        if not self.db.is_available:
            logger.warning("⚠️  Supabase not available, validation log not stored")
            return

        try:
            self.db.client.table('validation_logs').insert(log_data).execute()
            logger.debug(f"✅ Validation log stored: {log_data['log_type']}")
        except Exception as e:
            logger.error(f"❌ Failed to write validation log to database: {e}")


# Global validation logger instance
validation_logger = ValidationLogger()
