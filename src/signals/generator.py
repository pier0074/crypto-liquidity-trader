"""
Signal generation system for creating trade signals from detected patterns
"""
import pandas as pd
from datetime import datetime, timedelta
import logging
from src.utils import calculate_position_size, calculate_risk_reward

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates trading signals from detected patterns"""

    def __init__(self, config):
        """
        Initialize signal generator

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.signal_config = config.get("signals", {})
        self.risk_config = config.get("risk_management", {})

        # Signal parameters
        self.min_risk_reward = self.signal_config.get("min_risk_reward", 2.0)
        self.stop_loss_atr_multiplier = self.signal_config.get("stop_loss_atr_multiplier", 1.5)
        self.take_profit_levels = self.signal_config.get("take_profit_levels", [2, 3, 4])

        # Risk management
        self.max_risk_percent = self.risk_config.get("max_risk_per_trade_percent", 1.0)
        self.account_size = self.risk_config.get("account_size", 10000)

    def generate_signals_from_patterns(self, patterns, symbol, timeframe, current_df):
        """
        Generate trading signals from detected patterns

        Args:
            patterns: List of detected patterns
            symbol: Trading pair symbol
            timeframe: Timeframe string
            current_df: Current OHLCV DataFrame for context

        Returns:
            List of signal dictionaries
        """
        signals = []

        for pattern in patterns:
            # Generate signal based on pattern type
            if pattern["pattern_type"] == "fair_value_gap":
                signal = self._generate_fvg_signal(pattern, symbol, timeframe, current_df)
                if signal:
                    signals.append(signal)

            # Add more pattern types here as they're implemented

        logger.info(f"Generated {len(signals)} signals from {len(patterns)} patterns")
        return signals

    def _generate_fvg_signal(self, pattern, symbol, timeframe, df):
        """
        Generate trading signal from Fair Value Gap pattern

        Args:
            pattern: FVG pattern dictionary
            symbol: Trading pair
            timeframe: Timeframe
            df: OHLCV DataFrame

        Returns:
            Signal dictionary or None
        """
        current_price = df.iloc[-1]["close"]
        direction = pattern["direction"]

        # Get entry zone from pattern
        gap_low = pattern["price_low"]
        gap_high = pattern["price_high"]

        # Calculate ATR for stop loss placement
        atr = self._calculate_atr(df, period=14)

        if direction == "bullish":
            # For bullish FVG: Wait for price to fill into gap, then go long
            entry_price = gap_low + (gap_high - gap_low) * 0.25  # Lower 25% of gap

            # Stop loss below the gap
            stop_loss = gap_low - (atr * self.stop_loss_atr_multiplier)

            # Take profit levels based on R/R ratios
            risk = entry_price - stop_loss
            take_profit_1 = entry_price + (risk * self.take_profit_levels[0])
            take_profit_2 = entry_price + (risk * self.take_profit_levels[1]) if len(self.take_profit_levels) > 1 else None
            take_profit_3 = entry_price + (risk * self.take_profit_levels[2]) if len(self.take_profit_levels) > 2 else None

            trade_direction = "long"

        else:  # bearish
            # For bearish FVG: Wait for price to fill into gap, then go short
            entry_price = gap_high - (gap_high - gap_low) * 0.25  # Upper 25% of gap

            # Stop loss above the gap
            stop_loss = gap_high + (atr * self.stop_loss_atr_multiplier)

            # Take profit levels based on R/R ratios
            risk = stop_loss - entry_price
            take_profit_1 = entry_price - (risk * self.take_profit_levels[0])
            take_profit_2 = entry_price - (risk * self.take_profit_levels[1]) if len(self.take_profit_levels) > 1 else None
            take_profit_3 = entry_price - (risk * self.take_profit_levels[2]) if len(self.take_profit_levels) > 2 else None

            trade_direction = "short"

        # Calculate R/R ratio
        rr_ratio = calculate_risk_reward(entry_price, stop_loss, take_profit_1)

        # Only generate signal if R/R meets minimum
        if rr_ratio < self.min_risk_reward:
            logger.debug(f"Signal rejected: R/R {rr_ratio:.2f} < {self.min_risk_reward}")
            return None

        # Calculate position size
        risk_amount = self.account_size * (self.max_risk_percent / 100)
        position_size = calculate_position_size(entry_price, stop_loss, risk_amount)

        # Create signal
        signal = {
            "pattern_id": None,  # Will be set when pattern is saved to DB
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": trade_direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit_1": take_profit_1,
            "take_profit_2": take_profit_2,
            "take_profit_3": take_profit_3,
            "risk_reward_ratio": rr_ratio,
            "risk_amount": risk_amount,
            "position_size": position_size,
            "status": "pending",
            "notified": False,
            "valid_until": datetime.utcnow() + timedelta(hours=24),  # Signal valid for 24h
            "notes": f"FVG {direction} - Gap: {gap_low:.8f} to {gap_high:.8f}",
        }

        logger.info(f"Generated {trade_direction} signal for {symbol} @ {entry_price:.8f} (R/R: {rr_ratio:.2f})")
        return signal

    def _calculate_atr(self, df, period=14):
        """
        Calculate Average True Range (ATR)

        Args:
            df: OHLCV DataFrame
            period: ATR period

        Returns:
            ATR value
        """
        if len(df) < period:
            # Fallback to simple range
            return (df["high"].max() - df["low"].min()) / len(df)

        # Calculate True Range
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # Calculate ATR
        atr = tr.rolling(window=period).mean().iloc[-1]

        return atr

    def check_signal_validity(self, signal, current_price, current_time):
        """
        Check if a signal is still valid

        Args:
            signal: Signal dictionary
            current_price: Current market price
            current_time: Current datetime

        Returns:
            Tuple (is_valid, reason)
        """
        # Check if expired
        if signal.get("valid_until") and current_time > signal["valid_until"]:
            return False, "expired"

        # Check if price has moved too far from entry
        entry_price = signal["entry_price"]
        price_diff_percent = abs(current_price - entry_price) / entry_price * 100

        if price_diff_percent > 5:  # 5% threshold
            return False, "price_moved_away"

        # Check if stop loss would be hit
        if signal["direction"] == "long":
            if current_price <= signal["stop_loss"]:
                return False, "stop_loss_hit"
        else:  # short
            if current_price >= signal["stop_loss"]:
                return False, "stop_loss_hit"

        return True, "valid"

    def format_signal_for_notification(self, signal):
        """
        Format signal for email/notification

        Args:
            signal: Signal dictionary

        Returns:
            Formatted string
        """
        direction_emoji = "📈" if signal["direction"] == "long" else "📉"

        message = f"""
{direction_emoji} NEW TRADING SIGNAL

Symbol: {signal['symbol']}
Timeframe: {signal['timeframe']}
Direction: {signal['direction'].upper()}

ENTRY: {signal['entry_price']:.8f}
STOP LOSS: {signal['stop_loss']:.8f}

TAKE PROFITS:
  TP1: {signal['take_profit_1']:.8f} (R/R: {self.take_profit_levels[0]}:1)
"""

        if signal.get('take_profit_2'):
            message += f"  TP2: {signal['take_profit_2']:.8f} (R/R: {self.take_profit_levels[1]}:1)\n"

        if signal.get('take_profit_3'):
            message += f"  TP3: {signal['take_profit_3']:.8f} (R/R: {self.take_profit_levels[2]}:1)\n"

        message += f"""
Risk/Reward: {signal['risk_reward_ratio']:.2f}:1
Position Size: {signal['position_size']:.4f} {signal['symbol'].split('/')[0]}
Risk Amount: ${signal['risk_amount']:.2f}

Notes: {signal.get('notes', '')}

Valid Until: {signal.get('valid_until', 'N/A')}
"""

        return message

    def get_active_signals_summary(self, signals):
        """
        Get summary of active signals

        Args:
            signals: List of signal dictionaries

        Returns:
            Summary dictionary
        """
        if not signals:
            return {
                "total": 0,
                "long": 0,
                "short": 0,
                "total_risk": 0,
            }

        summary = {
            "total": len(signals),
            "long": sum(1 for s in signals if s["direction"] == "long"),
            "short": sum(1 for s in signals if s["direction"] == "short"),
            "total_risk": sum(s.get("risk_amount", 0) for s in signals),
            "symbols": list(set(s["symbol"] for s in signals)),
        }

        return summary
