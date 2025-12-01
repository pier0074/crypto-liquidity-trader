"""
Data collection module for fetching OHLCV data from exchanges
"""
import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time
import logging

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects OHLCV data from cryptocurrency exchanges"""

    def __init__(self, exchange_name="kucoin", api_key=None, api_secret=None, password=None):
        """
        Initialize data collector

        Args:
            exchange_name: Name of the exchange (default: kucoin)
            api_key: API key (optional, not needed for public data)
            api_secret: API secret (optional)
            password: API password (optional, KuCoin specific)
        """
        self.exchange_name = exchange_name

        # Initialize exchange
        exchange_class = getattr(ccxt, exchange_name)
        config = {}

        if api_key and api_secret:
            config["apiKey"] = api_key
            config["secret"] = api_secret
            if password:  # KuCoin requires password
                config["password"] = password

        self.exchange = exchange_class(config)
        self.exchange.load_markets()

        logger.info(f"Initialized {exchange_name} data collector")

    def fetch_ohlcv(self, symbol, timeframe="1m", since=None, limit=500):
        """
        Fetch OHLCV data from exchange

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe string (e.g., '1m', '5m', '1h')
            since: Start timestamp in milliseconds (optional)
            limit: Number of candles to fetch (max varies by exchange)

        Returns:
            List of OHLCV data [timestamp, open, high, low, close, volume]
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since, limit)
            logger.debug(f"Fetched {len(ohlcv)} candles for {symbol} {timeframe}")
            return ohlcv
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
            raise

    def fetch_ohlcv_range(self, symbol, timeframe, start_date, end_date=None):
        """
        Fetch OHLCV data for a date range by making multiple requests

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe string (e.g., '1m', '5m', '1h')
            start_date: Start datetime
            end_date: End datetime (default: now)

        Returns:
            List of OHLCV data
        """
        if end_date is None:
            end_date = datetime.utcnow()

        all_ohlcv = []
        current_time = int(start_date.timestamp() * 1000)
        end_time = int(end_date.timestamp() * 1000)

        # Determine appropriate limit based on timeframe to avoid too many requests
        limit = 1000  # Most exchanges support up to 1000 or 1500

        logger.info(f"Fetching {symbol} {timeframe} from {start_date} to {end_date}")

        while current_time < end_time:
            try:
                ohlcv = self.fetch_ohlcv(symbol, timeframe, current_time, limit)

                if not ohlcv:
                    break

                all_ohlcv.extend(ohlcv)

                # Update current_time to last candle timestamp + 1
                current_time = ohlcv[-1][0] + 1

                # Rate limiting
                time.sleep(self.exchange.rateLimit / 1000)

                logger.debug(f"Fetched up to {datetime.fromtimestamp(current_time / 1000)}")

            except Exception as e:
                logger.error(f"Error fetching data range: {e}")
                break

        logger.info(f"Fetched total {len(all_ohlcv)} candles for {symbol} {timeframe}")
        return all_ohlcv

    def ohlcv_to_dataframe(self, ohlcv):
        """
        Convert OHLCV list to pandas DataFrame

        Args:
            ohlcv: List of OHLCV data

        Returns:
            Pandas DataFrame
        """
        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    def fetch_multiple_pairs(self, symbols, timeframe, start_date, end_date=None):
        """
        Fetch OHLCV data for multiple trading pairs

        Args:
            symbols: List of trading pairs
            timeframe: Timeframe string
            start_date: Start datetime
            end_date: End datetime (default: now)

        Returns:
            Dict mapping symbol to OHLCV data
        """
        results = {}

        for symbol in symbols:
            try:
                logger.info(f"Fetching {symbol}...")
                ohlcv = self.fetch_ohlcv_range(symbol, timeframe, start_date, end_date)
                results[symbol] = ohlcv

                # Rate limiting between pairs
                time.sleep(self.exchange.rateLimit / 1000)

            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                results[symbol] = []

        return results

    def save_to_database(self, db, symbol, timeframe, ohlcv):
        """
        Save OHLCV data to database

        Args:
            db: Database instance
            symbol: Trading pair
            timeframe: Timeframe string
            ohlcv: OHLCV data (list or DataFrame)
        """
        # Convert to list of dicts
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv_list = ohlcv.to_dict("records")
        else:
            # Convert from raw OHLCV format
            ohlcv_list = []
            for candle in ohlcv:
                ohlcv_list.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "timestamp": datetime.fromtimestamp(candle[0] / 1000),
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4],
                    "volume": candle[5],
                })

        # Add symbol and timeframe if from DataFrame
        if isinstance(ohlcv, pd.DataFrame):
            for item in ohlcv_list:
                item["symbol"] = symbol
                item["timeframe"] = timeframe

        try:
            db.bulk_insert_ohlcv(ohlcv_list)
            logger.info(f"Saved {len(ohlcv_list)} candles to database for {symbol} {timeframe}")
        except Exception as e:
            logger.error(f"Error saving to database: {e}")

    def get_top_volume_pairs(self, base_currency="USDT", min_volume_24h=1000000, limit=50):
        """
        Get top trading pairs by 24h volume

        Args:
            base_currency: Base currency to filter (default: USDT)
            min_volume_24h: Minimum 24h volume in USD
            limit: Maximum number of pairs to return

        Returns:
            List of trading pair symbols sorted by volume
        """
        try:
            tickers = self.exchange.fetch_tickers()

            # Filter and sort by volume
            pairs = []
            for symbol, ticker in tickers.items():
                if base_currency in symbol and ticker.get("quoteVolume"):
                    volume_24h = ticker["quoteVolume"]
                    if volume_24h >= min_volume_24h:
                        pairs.append({
                            "symbol": symbol,
                            "volume": volume_24h
                        })

            # Sort by volume descending
            pairs.sort(key=lambda x: x["volume"], reverse=True)

            # Return top N symbols
            top_pairs = [p["symbol"] for p in pairs[:limit]]

            logger.info(f"Found {len(top_pairs)} pairs with volume > ${min_volume_24h:,.0f}")
            return top_pairs

        except Exception as e:
            logger.error(f"Error getting top volume pairs: {e}")
            return []


def aggregate_timeframe(df_1m, target_timeframe):
    """
    Aggregate 1-minute data to higher timeframes

    Args:
        df_1m: DataFrame with 1-minute OHLCV data
        target_timeframe: Target timeframe (e.g., '5m', '15m', '1h')

    Returns:
        DataFrame with aggregated data
    """
    # Convert timeframe to pandas offset
    timeframe_map = {
        "5m": "5T",
        "15m": "15T",
        "30m": "30T",
        "1h": "1H",
        "2h": "2H",
        "4h": "4H",
        "6h": "6H",
        "12h": "12H",
        "1d": "1D",
        "1w": "1W",
    }

    if target_timeframe not in timeframe_map:
        raise ValueError(f"Unsupported target timeframe: {target_timeframe}")

    offset = timeframe_map[target_timeframe]

    # Set timestamp as index
    df = df_1m.copy()
    df.set_index("timestamp", inplace=True)

    # Aggregate
    aggregated = df.resample(offset).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()

    # Reset index
    aggregated.reset_index(inplace=True)

    return aggregated
