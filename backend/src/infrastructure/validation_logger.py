"""Validation logger for tracking Claude AI misclassifications."""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationLogger:
    """Logs validation failures when Claude misclassifies substances."""

    def __init__(self, log_dir: str = "logs/validation"):
        """Initialize validation logger.

        Args:
            log_dir: Directory to store validation logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with date
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"validation_{today}.jsonl"

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
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "invalid_allergen",
            "substance_name": substance_name,
            "severity": severity,
            "confidence": confidence,
            "source": source,
            "product_url": product_url,
            "product_name": product_name
        }

        self._write_log(log_entry)
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
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "invalid_pfas",
            "substance_name": substance_name,
            "cas_number": cas_number,
            "confidence": confidence,
            "source": source,
            "product_url": product_url,
            "product_name": product_name
        }

        self._write_log(log_entry)
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
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "reclassified_substance",
            "substance_name": substance_name,
            "original_category": original_category,
            "new_category": new_category,
            "reason": reason,
            "product_url": product_url,
            "product_name": product_name
        }

        self._write_log(log_entry)
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
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "validation_summary",
            "product_name": product_name,
            "product_url": product_url,
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

        self._write_log(log_entry)

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

    def _write_log(self, log_entry: Dict[str, Any]) -> None:
        """Write log entry to file.

        Args:
            log_entry: Dictionary to write as JSON line
        """
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write validation log: {e}")

    def get_daily_stats(self) -> Dict[str, Any]:
        """Get statistics from today's validation logs.

        Returns:
            Dictionary with statistics
        """
        if not self.log_file.exists():
            return {
                "total_validations": 0,
                "invalid_allergens": 0,
                "invalid_pfas": 0,
                "reclassifications": 0
            }

        stats = {
            "total_validations": 0,
            "invalid_allergens": 0,
            "invalid_pfas": 0,
            "reclassifications": 0,
            "substances_flagged": set()
        }

        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    entry = json.loads(line.strip())

                    if entry["type"] == "validation_summary":
                        stats["total_validations"] += 1
                    elif entry["type"] == "invalid_allergen":
                        stats["invalid_allergens"] += 1
                        stats["substances_flagged"].add(entry["substance_name"])
                    elif entry["type"] == "invalid_pfas":
                        stats["invalid_pfas"] += 1
                        stats["substances_flagged"].add(entry["substance_name"])
                    elif entry["type"] == "reclassified_substance":
                        stats["reclassifications"] += 1

            stats["substances_flagged"] = list(stats["substances_flagged"])
            return stats
        except Exception as e:
            logger.error(f"Failed to read validation logs: {e}")
            return stats


# Global validation logger instance
validation_logger = ValidationLogger()
