#!/usr/bin/env python3
"""
Backtesting script - test strategy on historical data
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config, setup_logging
from src.data.database import init_database
from src.patterns.fair_value_gap import FairValueGap
from src.signals.generator import SignalGenerator
from src.backtesting.engine import BacktestEngine
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def main():
    # Load configuration
    config = load_config()
    setup_logging(config)

    logger.info("=" * 60)
    logger.info("Backtesting Strategy on Historical Data")
    logger.info("=" * 60)

    # Initialize components
    db = init_database(config)
    pattern_detector = FairValueGap(config.get("patterns", {}).get("fair_value_gap", {}))
    signal_generator = SignalGenerator(config)
    backtest_engine = BacktestEngine(config)

    # Get configuration
    backtest_config = config.get("backtesting", {})
    start_date_str = backtest_config.get("start_date", "2024-01-01")
    end_date_str = backtest_config.get("end_date")

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    else:
        end_date = datetime.utcnow()

    logger.info(f"Backtest period: {start_date} to {end_date}")

    # Get symbols and timeframes to test
    symbols = config.get("trading_pairs", ["BTC/USDT", "ETH/USDT"])[:5]  # Test on first 5 pairs
    timeframes = config.get("timeframes", ["1h", "4h"])  # Focus on higher timeframes for backtest

    logger.info(f"Testing {len(symbols)} symbols on {len(timeframes)} timeframes")

    # Fetch historical data and generate signals
    all_signals = []
    ohlcv_data = {}

    for symbol in symbols:
        logger.info(f"\nProcessing {symbol}...")

        for timeframe in timeframes:
            try:
                # Get OHLCV data from database
                ohlcv_records = db.get_ohlcv(
                    symbol, timeframe,
                    start_time=start_date,
                    end_time=end_date
                )

                if not ohlcv_records or len(ohlcv_records) < 100:
                    logger.warning(f"Insufficient data for {symbol} {timeframe}")
                    logger.info(f"Please run: python scripts/fetch_historical.py")
                    continue

                # Convert to DataFrame
                import pandas as pd
                df = pd.DataFrame([{
                    "timestamp": r.timestamp,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume
                } for r in ohlcv_records])

                # Store for backtest
                ohlcv_data[(symbol, timeframe)] = df

                # Detect patterns
                patterns = pattern_detector.detect(df)
                logger.info(f"  {timeframe}: Found {len(patterns)} patterns")

                # Generate signals
                signals = signal_generator.generate_signals_from_patterns(
                    patterns, symbol, timeframe, df
                )
                logger.info(f"  {timeframe}: Generated {len(signals)} signals")

                # Add generated_at timestamp based on pattern end time
                for i, signal in enumerate(signals):
                    if i < len(patterns):
                        signal["generated_at"] = patterns[i]["end_timestamp"]
                    else:
                        signal["generated_at"] = df.iloc[-1]["timestamp"]

                all_signals.extend(signals)

            except Exception as e:
                logger.error(f"Error processing {symbol} {timeframe}: {e}")
                continue

    logger.info(f"\nTotal signals generated: {len(all_signals)}")

    if not all_signals:
        logger.error("No signals generated. Cannot run backtest.")
        logger.info("Make sure you have historical data. Run: python scripts/fetch_historical.py")
        return

    # Run backtest
    logger.info("\nRunning backtest...")
    results = backtest_engine.run_backtest(all_signals, ohlcv_data)

    # Print results
    backtest_engine.print_summary(results)

    # Print sample trades
    if results["trades"]:
        print("\nSample Trades (first 10):")
        print("-" * 60)
        for trade in results["trades"][:10]:
            print(f"{trade['symbol']:12} {trade['direction']:5} "
                  f"Entry: {trade['entry_price']:10.8f} "
                  f"Exit: {trade['exit_price']:10.8f} "
                  f"P/L: ${trade['pnl']:8.2f} ({trade['pnl_percent']:6.2f}%) "
                  f"Reason: {trade['exit_reason']}")


if __name__ == "__main__":
    main()
