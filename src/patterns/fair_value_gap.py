"""
Fair Value Gap (FVG) / Imbalance pattern detector
"""
from .base import BasePattern
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class FairValueGap(BasePattern):
    """
    Detects Fair Value Gaps (FVG) / Imbalances in price action

    A Fair Value Gap occurs when there's a gap between three consecutive candles:
    - Bullish FVG: Gap between candle[0].high and candle[2].low (candle[1] is bullish impulse)
    - Bearish FVG: Gap between candle[0].low and candle[2].high (candle[1] is bearish impulse)

    These gaps represent areas where price moved too fast with minimal trading,
    creating an imbalance that price often returns to fill.
    """

    def __init__(self, config=None):
        super().__init__(config)

        # Configuration
        self.min_gap_percentage = self.config.get("min_gap_percentage", 0.1)
        self.lookback_candles = self.config.get("lookback_candles", 100)

    def detect(self, df):
        """
        Detect Fair Value Gaps in OHLCV data

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of detected FVG patterns
        """
        df = self.prepare_dataframe(df)

        if len(df) < 3:
            return []

        patterns = []

        # Only analyze recent candles (lookback)
        start_idx = max(0, len(df) - self.lookback_candles)

        # Iterate through candles looking for gaps
        for i in range(start_idx, len(df) - 2):
            candle_0 = df.iloc[i]
            candle_1 = df.iloc[i + 1]
            candle_2 = df.iloc[i + 2]

            # Check for Bullish FVG
            bullish_fvg = self._detect_bullish_fvg(candle_0, candle_1, candle_2)
            if bullish_fvg:
                patterns.append(bullish_fvg)

            # Check for Bearish FVG
            bearish_fvg = self._detect_bearish_fvg(candle_0, candle_1, candle_2)
            if bearish_fvg:
                patterns.append(bearish_fvg)

        # Filter overlapping patterns
        patterns = self.filter_overlapping_patterns(patterns)

        logger.info(f"Detected {len(patterns)} Fair Value Gaps")
        return patterns

    def _detect_bullish_fvg(self, candle_0, candle_1, candle_2):
        """
        Detect bullish Fair Value Gap

        Bullish FVG occurs when:
        - There's a gap between candle[0].high and candle[2].low
        - Candle[1] is a strong bullish candle (impulse move up)
        """
        gap_bottom = candle_0["high"]
        gap_top = candle_2["low"]

        # Check if there's a gap
        if gap_top > gap_bottom:
            gap_size = gap_top - gap_bottom
            gap_percentage = (gap_size / candle_1["close"]) * 100

            # Check if gap meets minimum size requirement
            if gap_percentage >= self.min_gap_percentage:
                # Check if candle[1] is bullish (impulse)
                candle_1_is_bullish = candle_1["close"] > candle_1["open"]
                candle_1_body_size = abs(candle_1["close"] - candle_1["open"])
                candle_1_range = candle_1["high"] - candle_1["low"]

                # Strong bullish candle: body is significant portion of range
                if candle_1_is_bullish and candle_1_body_size / candle_1_range > 0.5:
                    # Calculate confidence
                    confidence = self.calculate_confidence(
                        gap_percentage=gap_percentage,
                        impulse_strength=candle_1_body_size / candle_1_range
                    )

                    pattern = {
                        "pattern_type": "fair_value_gap",
                        "direction": "bullish",
                        "start_timestamp": candle_0["timestamp"],
                        "end_timestamp": candle_2["timestamp"],
                        "price_high": gap_top,
                        "price_low": gap_bottom,
                        "gap_size": gap_size,
                        "gap_percentage": gap_percentage,
                        "confidence_score": confidence,
                        "is_filled": False,
                    }

                    return pattern

        return None

    def _detect_bearish_fvg(self, candle_0, candle_1, candle_2):
        """
        Detect bearish Fair Value Gap

        Bearish FVG occurs when:
        - There's a gap between candle[0].low and candle[2].high
        - Candle[1] is a strong bearish candle (impulse move down)
        """
        gap_top = candle_0["low"]
        gap_bottom = candle_2["high"]

        # Check if there's a gap
        if gap_top > gap_bottom:
            gap_size = gap_top - gap_bottom
            gap_percentage = (gap_size / candle_1["close"]) * 100

            # Check if gap meets minimum size requirement
            if gap_percentage >= self.min_gap_percentage:
                # Check if candle[1] is bearish (impulse)
                candle_1_is_bearish = candle_1["close"] < candle_1["open"]
                candle_1_body_size = abs(candle_1["close"] - candle_1["open"])
                candle_1_range = candle_1["high"] - candle_1["low"]

                # Strong bearish candle: body is significant portion of range
                if candle_1_is_bearish and candle_1_body_size / candle_1_range > 0.5:
                    # Calculate confidence
                    confidence = self.calculate_confidence(
                        gap_percentage=gap_percentage,
                        impulse_strength=candle_1_body_size / candle_1_range
                    )

                    pattern = {
                        "pattern_type": "fair_value_gap",
                        "direction": "bearish",
                        "start_timestamp": candle_0["timestamp"],
                        "end_timestamp": candle_2["timestamp"],
                        "price_high": gap_top,
                        "price_low": gap_bottom,
                        "gap_size": gap_size,
                        "gap_percentage": gap_percentage,
                        "confidence_score": confidence,
                        "is_filled": False,
                    }

                    return pattern

        return None

    def calculate_confidence(self, gap_percentage, impulse_strength):
        """
        Calculate confidence score for FVG

        Args:
            gap_percentage: Size of gap as percentage
            impulse_strength: Strength of impulse candle (body/range ratio)

        Returns:
            Confidence score between 0 and 1
        """
        # Base confidence
        confidence = 0.5

        # Larger gaps are more significant
        if gap_percentage > 0.5:
            confidence += 0.2
        if gap_percentage > 1.0:
            confidence += 0.1

        # Stronger impulse candles are more reliable
        if impulse_strength > 0.7:
            confidence += 0.1
        if impulse_strength > 0.9:
            confidence += 0.1

        return min(confidence, 1.0)

    def check_if_filled(self, pattern, current_price):
        """
        Check if a Fair Value Gap has been filled by price

        Args:
            pattern: FVG pattern dictionary
            current_price: Current price to check

        Returns:
            True if filled, False otherwise
        """
        gap_low = pattern["price_low"]
        gap_high = pattern["price_high"]

        # Consider filled if price has entered the gap zone
        return gap_low <= current_price <= gap_high

    def get_entry_zone(self, pattern):
        """
        Get the ideal entry zone for trading this FVG

        Args:
            pattern: FVG pattern dictionary

        Returns:
            Dictionary with entry_low and entry_high prices
        """
        gap_low = pattern["price_low"]
        gap_high = pattern["price_high"]

        if pattern["direction"] == "bullish":
            # For bullish FVG, enter when price fills back into the gap
            # Prefer entering at lower part of gap for better R/R
            return {
                "entry_low": gap_low,
                "entry_high": gap_low + (gap_high - gap_low) * 0.5,  # Lower 50% of gap
                "optimal_entry": gap_low + (gap_high - gap_low) * 0.25,  # Lower 25%
            }
        else:  # bearish
            # For bearish FVG, enter when price fills back into the gap
            # Prefer entering at upper part of gap for better R/R
            return {
                "entry_low": gap_high - (gap_high - gap_low) * 0.5,  # Upper 50% of gap
                "entry_high": gap_high,
                "optimal_entry": gap_high - (gap_high - gap_low) * 0.25,  # Upper 25%
            }
