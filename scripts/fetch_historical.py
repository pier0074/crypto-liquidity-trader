#!/usr/bin/env python3
"""
Script to fetch historical OHLCV data from exchange
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config, setup_logging
from src.data.database import init_database
from src.data.collector import DataCollector, aggregate_timeframe
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def main():
    # Load configuration
    config = load_config()
    setup_logging(config)

    logger.info("=" * 60)
    logger.info("Fetching Historical Data")
    logger.info("=" * 60)

    # Initialize database
    db = init_database(config)

    # Initialize data collector
    exchange_config = config.get("exchange", {})
    collector = DataCollector(
        exchange_name=exchange_config.get("name", "kucoin"),
        api_key=exchange_config.get("api_key"),
        api_secret=exchange_config.get("api_secret"),
        password=exchange_config.get("password"),
    )

    # Get trading pairs
    trading_pairs = config.get("trading_pairs", [])
    if not trading_pairs:
        logger.info("No trading pairs in config, fetching top volume pairs...")
        scanner_config = config.get("scanner", {})
        min_volume = scanner_config.get("min_volume_24h", 1000000)
        trading_pairs = collector.get_top_volume_pairs(
            base_currency="USDT",
            min_volume_24h=min_volume,
            limit=50
        )
        logger.info(f"Found {len(trading_pairs)} pairs: {', '.join(trading_pairs[:10])}...")

    # Get timeframes
    timeframes = config.get("timeframes", ["1m", "5m", "15m", "1h", "4h", "1d"])

    # Date range
    backtest_config = config.get("backtesting", {})
    start_date_str = backtest_config.get("start_date", "2024-01-01")
    end_date_str = backtest_config.get("end_date")

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    else:
        end_date = datetime.utcnow()

    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Trading pairs: {len(trading_pairs)}")
    logger.info(f"Timeframes: {', '.join(timeframes)}")

    # Fetch data for each pair
    for i, symbol in enumerate(trading_pairs, 1):
        logger.info(f"\n[{i}/{len(trading_pairs)}] Processing {symbol}")

        try:
            # Fetch 1-minute data first
            logger.info(f"Fetching 1m data for {symbol}...")
            ohlcv_1m = collector.fetch_ohlcv_range(
                symbol,
                "1m",
                start_date,
                end_date
            )

            if not ohlcv_1m:
                logger.warning(f"No data fetched for {symbol}")
                continue

            # Convert to DataFrame for aggregation
            df_1m = collector.ohlcv_to_dataframe(ohlcv_1m)

            # Save 1m data
            if "1m" in timeframes:
                collector.save_to_database(db, symbol, "1m", ohlcv_1m)

            # Aggregate to other timeframes
            for timeframe in timeframes:
                if timeframe == "1m":
                    continue

                try:
                    logger.info(f"Aggregating to {timeframe}...")
                    df_aggregated = aggregate_timeframe(df_1m, timeframe)

                    # Save aggregated data
                    collector.save_to_database(db, symbol, timeframe, df_aggregated)

                except Exception as e:
                    logger.error(f"Error aggregating {symbol} to {timeframe}: {e}")

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            continue

    logger.info("\n" + "=" * 60)
    logger.info("Historical data fetch completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
