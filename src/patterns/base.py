"""
Base class for pattern detection
"""
from abc import ABC, abstractmethod
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class BasePattern(ABC):
    """Abstract base class for pattern detectors"""

    def __init__(self, config=None):
        """
        Initialize pattern detector

        Args:
            config: Configuration dictionary for this pattern
        """
        self.config = config or {}
        self.name = self.__class__.__name__

    @abstractmethod
    def detect(self, df):
        """
        Detect patterns in OHLCV data

        Args:
            df: DataFrame with OHLCV data (columns: timestamp, open, high, low, close, volume)

        Returns:
            List of detected patterns (dicts with pattern information)
        """
        pass

    def prepare_dataframe(self, df):
        """
        Prepare DataFrame for pattern detection

        Args:
            df: Input DataFrame

        Returns:
            Prepared DataFrame
        """
        # Make a copy
        df = df.copy()

        # Ensure timestamp column
        if "timestamp" not in df.columns and df.index.name == "timestamp":
            df.reset_index(inplace=True)

        # Sort by timestamp
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    def validate_pattern(self, pattern):
        """
        Validate pattern data

        Args:
            pattern: Pattern dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = [
            "pattern_type",
            "direction",
            "start_timestamp",
            "end_timestamp",
            "price_high",
            "price_low",
        ]

        for field in required_fields:
            if field not in pattern:
                logger.warning(f"Pattern missing required field: {field}")
                return False

        return True

    def filter_overlapping_patterns(self, patterns):
        """
        Filter out overlapping patterns, keeping the strongest ones

        Args:
            patterns: List of pattern dicts

        Returns:
            Filtered list of patterns
        """
        if not patterns:
            return []

        # Sort by confidence score (if available) or gap size
        patterns.sort(
            key=lambda p: p.get("confidence_score", p.get("gap_size", 0)),
            reverse=True
        )

        filtered = []
        for pattern in patterns:
            # Check if this pattern overlaps with any already filtered patterns
            overlaps = False
            for existing in filtered:
                if self._patterns_overlap(pattern, existing):
                    overlaps = True
                    break

            if not overlaps:
                filtered.append(pattern)

        return filtered

    def _patterns_overlap(self, pattern1, pattern2):
        """
        Check if two patterns overlap in time

        Args:
            pattern1: First pattern dict
            pattern2: Second pattern dict

        Returns:
            True if patterns overlap, False otherwise
        """
        start1 = pattern1["start_timestamp"]
        end1 = pattern1["end_timestamp"]
        start2 = pattern2["start_timestamp"]
        end2 = pattern2["end_timestamp"]

        # Check for time overlap
        return not (end1 < start2 or end2 < start1)

    def calculate_confidence(self, **kwargs):
        """
        Calculate confidence score for a pattern

        Args:
            **kwargs: Pattern-specific parameters

        Returns:
            Confidence score between 0 and 1
        """
        # Base implementation, can be overridden by subclasses
        return 1.0
