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
            # Fetch 1-minute data with incremental saving and resume capability
            logger.info(f"Fetching 1m data for {symbol}...")
            ohlcv_1m = collector.fetch_ohlcv_range(
                symbol,
                "1m",
                start_date,
                end_date,
                db=db,  # Enable incremental saving
                save_frequency=10  # Save every 10 requests (~10,000 candles)
            )

            if not ohlcv_1m or len(ohlcv_1m) == 0:
                # Check if data already exists
                existing_count = db.get_ohlcv_count(symbol, "1m")
                if existing_count > 0:
                    logger.info(f"Loading {existing_count:,} existing candles from DB for aggregation...")
                    # Load from database for aggregation
                    ohlcv_from_db = db.get_ohlcv(symbol, "1m", start_date, end_date)
                    if ohlcv_from_db:
                        # Convert DB objects to list format
                        ohlcv_1m = [[
                            int(candle.timestamp.timestamp() * 1000),
                            candle.open,
                            candle.high,
                            candle.low,
                            candle.close,
                            candle.volume
                        ] for candle in ohlcv_from_db]
                else:
                    logger.warning(f"No data available for {symbol}")
                    continue

            # Convert to DataFrame for aggregation
            df_1m = collector.ohlcv_to_dataframe(ohlcv_1m)

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

        except KeyboardInterrupt:
            logger.info("\n⚠️  Interrupted by user. Progress has been saved to database.")
            logger.info("You can safely restart this script - it will resume from where it left off.")
            raise
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            continue

    logger.info("\n" + "=" * 60)
    logger.info("Historical data fetch completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
