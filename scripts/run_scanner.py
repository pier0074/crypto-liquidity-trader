#!/usr/bin/env python3
"""
Main scanner script - detects patterns and generates trading signals
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config, setup_logging
from src.data.database import init_database
from src.data.collector import DataCollector
from src.patterns.fair_value_gap import FairValueGap
from src.signals.generator import SignalGenerator
from src.notifications.email_notifier import EmailNotifier
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)


class PatternScanner:
    """Main scanner class that orchestrates pattern detection and signal generation"""

    def __init__(self, config):
        """
        Initialize scanner with configuration

        Args:
            config: Configuration dictionary
        """
        self.config = config

        # Initialize components
        logger.info("Initializing components...")

        self.db = init_database(config)

        exchange_config = config.get("exchange", {})
        self.collector = DataCollector(
            exchange_name=exchange_config.get("name", "kucoin"),
            api_key=exchange_config.get("api_key"),
            api_secret=exchange_config.get("api_secret"),
            password=exchange_config.get("password"),
        )

        # Initialize pattern detectors
        self.pattern_detectors = {}
        patterns_config = config.get("patterns", {})

        if patterns_config.get("fair_value_gap", {}).get("enabled", True):
            self.pattern_detectors["fair_value_gap"] = FairValueGap(
                patterns_config.get("fair_value_gap", {})
            )
            logger.info("Fair Value Gap detector enabled")

        # Initialize signal generator
        self.signal_generator = SignalGenerator(config)

        # Initialize notifier
        self.notifier = EmailNotifier(config)

        # Get trading pairs and timeframes
        self.trading_pairs = config.get("trading_pairs", [])
        if not self.trading_pairs:
            logger.info("No trading pairs configured, fetching top volume pairs...")
            scanner_config = config.get("scanner", {})
            min_volume = scanner_config.get("min_volume_24h", 1000000)
            self.trading_pairs = self.collector.get_top_volume_pairs(
                base_currency="USDT",
                min_volume_24h=min_volume,
                limit=50
            )

        self.timeframes = config.get("timeframes", ["1m", "5m", "15m", "1h", "4h", "1d"])

        logger.info(f"Monitoring {len(self.trading_pairs)} pairs on {len(self.timeframes)} timeframes")

    def scan_symbol_timeframe(self, symbol, timeframe):
        """
        Scan a single symbol/timeframe combination

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string

        Returns:
            Dictionary with patterns and signals
        """
        try:
            # Fetch recent OHLCV data
            logger.debug(f"Fetching {symbol} {timeframe}...")
            lookback_hours = self._get_lookback_hours(timeframe)
            start_time = datetime.utcnow() - timedelta(hours=lookback_hours)

            ohlcv = self.collector.fetch_ohlcv_range(
                symbol, timeframe, start_time
            )

            if not ohlcv or len(ohlcv) < 100:
                logger.warning(f"Insufficient data for {symbol} {timeframe}")
                return {"patterns": [], "signals": []}

            # Convert to DataFrame
            df = self.collector.ohlcv_to_dataframe(ohlcv)

            # Save to database
            self.collector.save_to_database(self.db, symbol, timeframe, ohlcv)

            # Detect patterns
            all_patterns = []
            for pattern_type, detector in self.pattern_detectors.items():
                patterns = detector.detect(df)
                all_patterns.extend(patterns)

            logger.info(f"{symbol} {timeframe}: Found {len(all_patterns)} patterns")

            # Save patterns to database
            pattern_ids = []
            for pattern in all_patterns:
                pattern["symbol"] = symbol
                pattern["timeframe"] = timeframe
                pattern_id = self.db.save_pattern(pattern)
                pattern_ids.append(pattern_id)

            # Generate signals from patterns
            signals = self.signal_generator.generate_signals_from_patterns(
                all_patterns, symbol, timeframe, df
            )

            logger.info(f"{symbol} {timeframe}: Generated {len(signals)} signals")

            # Save signals to database
            for i, signal in enumerate(signals):
                if i < len(pattern_ids):
                    signal["pattern_id"] = pattern_ids[i]
                signal_id = self.db.save_signal(signal)
                signal["id"] = signal_id

            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "patterns": all_patterns,
                "signals": signals
            }

        except Exception as e:
            logger.error(f"Error scanning {symbol} {timeframe}: {e}")
            return {"patterns": [], "signals": []}

    def scan_all(self):
        """
        Scan all configured symbols and timeframes

        Returns:
            Dictionary with all results
        """
        logger.info("=" * 60)
        logger.info("Starting pattern scan...")
        logger.info("=" * 60)

        all_results = {
            "timestamp": datetime.utcnow(),
            "total_patterns": 0,
            "total_signals": 0,
            "signals_by_symbol": {}
        }

        # Scan each symbol/timeframe combination
        for symbol in self.trading_pairs:
            logger.info(f"\nScanning {symbol}...")

            symbol_results = {
                "patterns": 0,
                "signals": [],
                "timeframes": {}
            }

            for timeframe in self.timeframes:
                result = self.scan_symbol_timeframe(symbol, timeframe)

                symbol_results["patterns"] += len(result.get("patterns", []))
                symbol_results["signals"].extend(result.get("signals", []))
                symbol_results["timeframes"][timeframe] = result

                # Rate limiting
                time.sleep(self.collector.exchange.rateLimit / 1000)

            all_results["total_patterns"] += symbol_results["patterns"]
            all_results["total_signals"] += len(symbol_results["signals"])
            all_results["signals_by_symbol"][symbol] = symbol_results

            # Send notifications for new signals
            for signal in symbol_results["signals"]:
                if not signal.get("notified"):
                    self._send_signal_notification(signal)

        logger.info("\n" + "=" * 60)
        logger.info("Scan completed!")
        logger.info(f"Total patterns: {all_results['total_patterns']}")
        logger.info(f"Total signals: {all_results['total_signals']}")
        logger.info("=" * 60)

        return all_results

    def _send_signal_notification(self, signal):
        """
        Send notification for a signal

        Args:
            signal: Signal dictionary
        """
        try:
            # Format message
            message = self.signal_generator.format_signal_for_notification(signal)

            # Send email
            success = self.notifier.send_signal_notification(signal, message)

            if success:
                # Mark as notified in database
                self.db.update_signal_status(signal["id"], "pending")
                logger.info(f"Notification sent for signal {signal['id']}")
            else:
                logger.warning(f"Failed to send notification for signal {signal['id']}")

        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    def _get_lookback_hours(self, timeframe):
        """
        Get appropriate lookback period in hours for a timeframe

        Args:
            timeframe: Timeframe string

        Returns:
            Hours to look back
        """
        lookback_map = {
            "1m": 24,    # 1 day
            "5m": 48,    # 2 days
            "15m": 72,   # 3 days
            "1h": 168,   # 1 week
            "4h": 336,   # 2 weeks
            "1d": 720,   # 1 month
        }

        return lookback_map.get(timeframe, 168)


def main():
    # Load configuration
    config = load_config()
    setup_logging(config)

    logger.info("=" * 60)
    logger.info("Crypto Liquidity Trader - Pattern Scanner")
    logger.info("=" * 60)

    # Initialize scanner
    scanner = PatternScanner(config)

    # Get scan interval from config
    scanner_config = config.get("scanner", {})
    scan_interval = scanner_config.get("scan_interval_seconds", 60)

    # Run scan
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Single scan mode
        logger.info("Running single scan...")
        scanner.scan_all()
    else:
        # Continuous scanning mode
        logger.info(f"Running continuous scan (interval: {scan_interval}s)")
        logger.info("Press Ctrl+C to stop")

        try:
            while True:
                scanner.scan_all()
                logger.info(f"\nWaiting {scan_interval} seconds until next scan...")
                time.sleep(scan_interval)
        except KeyboardInterrupt:
            logger.info("\nScanner stopped by user")


if __name__ == "__main__":
    main()
