"""
Database models and operations using SQLAlchemy
"""
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class OHLCV(Base):
    """OHLCV candlestick data"""

    __tablename__ = "ohlcv"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uix_symbol_timeframe_timestamp"),
        Index("ix_symbol_timeframe_timestamp", "symbol", "timeframe", "timestamp"),
    )

    def __repr__(self):
        return f"<OHLCV {self.symbol} {self.timeframe} {self.timestamp} O:{self.open} H:{self.high} L:{self.low} C:{self.close}>"


class Pattern(Base):
    """Detected trading patterns"""

    __tablename__ = "patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    pattern_type = Column(String(50), nullable=False, index=True)  # 'fair_value_gap', 'liquidity_sweep', etc.
    direction = Column(String(10), nullable=False)  # 'bullish' or 'bearish'
    start_timestamp = Column(DateTime, nullable=False)
    end_timestamp = Column(DateTime, nullable=False)

    # Pattern-specific data (JSON-like fields)
    price_high = Column(Float)
    price_low = Column(Float)
    gap_size = Column(Float)
    gap_percentage = Column(Float)

    # Pattern status
    is_filled = Column(Boolean, default=False)
    filled_at = Column(DateTime, nullable=True)

    # Metadata
    confidence_score = Column(Float, default=1.0)
    data = Column(Text)  # JSON string for additional pattern-specific data
    detected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_pattern_symbol_timeframe_type", "symbol", "timeframe", "pattern_type"),
        Index("ix_pattern_detected_at", "detected_at"),
    )

    def __repr__(self):
        return f"<Pattern {self.pattern_type} {self.direction} {self.symbol} {self.timeframe} @ {self.start_timestamp}>"


class Signal(Base):
    """Generated trading signals"""

    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_id = Column(Integer, nullable=True)  # Link to pattern that generated this signal

    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)  # 'long' or 'short'

    # Entry and exit levels
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=True)
    take_profit_3 = Column(Float, nullable=True)

    # Risk/Reward
    risk_reward_ratio = Column(Float, nullable=False)
    risk_amount = Column(Float)  # In USD
    position_size = Column(Float)  # Amount to trade

    # Signal status
    status = Column(String(20), default="pending")  # pending, active, filled, cancelled, expired
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime, nullable=True)

    # Timestamps
    valid_until = Column(DateTime, nullable=True)  # Signal expiration
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_signal_symbol_status", "symbol", "status"),
        Index("ix_signal_generated_at", "generated_at"),
    )

    def __repr__(self):
        return f"<Signal {self.direction} {self.symbol} @ {self.entry_price} R/R:{self.risk_reward_ratio}>"


class Trade(Base):
    """Executed or tracked trades (for future automated trading and backtesting)"""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, nullable=True)  # Link to signal

    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(String(10), nullable=False)

    # Trade execution
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    position_size = Column(Float, nullable=False)

    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)

    # Trade results
    profit_loss = Column(Float, nullable=True)
    profit_loss_percent = Column(Float, nullable=True)
    status = Column(String(20), default="open")  # open, closed, cancelled
    exit_reason = Column(String(50), nullable=True)  # tp1, tp2, tp3, sl, manual

    # Fees
    entry_fee = Column(Float, default=0.0)
    exit_fee = Column(Float, default=0.0)

    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_trade_symbol_status", "symbol", "status"),
        Index("ix_trade_entry_time", "entry_time"),
    )

    def __repr__(self):
        return f"<Trade {self.direction} {self.symbol} @ {self.entry_price} P/L:{self.profit_loss}>"


class Database:
    """Database connection and operations manager"""

    def __init__(self, db_url="sqlite:///trading_data.db"):
        """
        Initialize database connection

        Args:
            db_url: SQLAlchemy database URL
                    Examples:
                    - SQLite: sqlite:///trading_data.db
                    - PostgreSQL: postgresql://user:password@localhost:5432/dbname
        """
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        logger.info(f"Database initialized: {db_url}")

    def create_tables(self):
        """Create all tables if they don't exist"""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created successfully")

    def drop_tables(self):
        """Drop all tables (use with caution!)"""
        Base.metadata.drop_all(self.engine)
        logger.warning("All database tables dropped")

    def get_session(self):
        """Get a new database session"""
        return self.Session()

    def bulk_insert_ohlcv(self, ohlcv_list):
        """
        Bulk insert OHLCV data

        Args:
            ohlcv_list: List of dicts with keys: symbol, timeframe, timestamp, open, high, low, close, volume
        """
        session = self.get_session()
        try:
            # Convert to OHLCV objects
            objects = []
            for data in ohlcv_list:
                obj = OHLCV(
                    symbol=data["symbol"],
                    timeframe=data["timeframe"],
                    timestamp=data["timestamp"],
                    open=data["open"],
                    high=data["high"],
                    low=data["low"],
                    close=data["close"],
                    volume=data["volume"],
                )
                objects.append(obj)

            # Bulk insert (ignore duplicates)
            session.bulk_save_objects(objects)
            session.commit()
            logger.info(f"Inserted {len(objects)} OHLCV records")
            return len(objects)
        except Exception as e:
            session.rollback()
            logger.error(f"Error bulk inserting OHLCV: {e}")
            raise
        finally:
            session.close()

    def get_ohlcv(self, symbol, timeframe, start_time=None, end_time=None, limit=None):
        """
        Retrieve OHLCV data

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string (1m, 5m, 1h, etc.)
            start_time: Start datetime (optional)
            end_time: End datetime (optional)
            limit: Maximum number of records (optional)

        Returns:
            List of OHLCV objects
        """
        session = self.get_session()
        try:
            query = session.query(OHLCV).filter(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == timeframe
            )

            if start_time:
                query = query.filter(OHLCV.timestamp >= start_time)
            if end_time:
                query = query.filter(OHLCV.timestamp <= end_time)

            query = query.order_by(OHLCV.timestamp.asc())

            if limit:
                query = query.limit(limit)

            return query.all()
        finally:
            session.close()

    def save_pattern(self, pattern_data):
        """
        Save a detected pattern

        Args:
            pattern_data: Dict with pattern information

        Returns:
            Pattern ID
        """
        session = self.get_session()
        try:
            pattern = Pattern(**pattern_data)
            session.add(pattern)
            session.commit()
            pattern_id = pattern.id
            logger.info(f"Saved pattern {pattern_id}: {pattern.pattern_type} {pattern.symbol}")
            return pattern_id
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving pattern: {e}")
            raise
        finally:
            session.close()

    def save_signal(self, signal_data):
        """
        Save a trading signal

        Args:
            signal_data: Dict with signal information

        Returns:
            Signal ID
        """
        session = self.get_session()
        try:
            signal = Signal(**signal_data)
            session.add(signal)
            session.commit()
            signal_id = signal.id
            logger.info(f"Saved signal {signal_id}: {signal.direction} {signal.symbol} @ {signal.entry_price}")
            return signal_id
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving signal: {e}")
            raise
        finally:
            session.close()

    def get_active_signals(self, symbol=None):
        """Get all active (pending) signals"""
        session = self.get_session()
        try:
            query = session.query(Signal).filter(Signal.status == "pending")
            if symbol:
                query = query.filter(Signal.symbol == symbol)
            return query.order_by(Signal.generated_at.desc()).all()
        finally:
            session.close()

    def update_signal_status(self, signal_id, status):
        """Update signal status"""
        session = self.get_session()
        try:
            signal = session.query(Signal).filter(Signal.id == signal_id).first()
            if signal:
                signal.status = status
                session.commit()
                logger.info(f"Updated signal {signal_id} status to {status}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating signal status: {e}")
            raise
        finally:
            session.close()

    def get_last_ohlcv_timestamp(self, symbol, timeframe):
        """
        Get the last (most recent) timestamp for a symbol/timeframe in the database

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string

        Returns:
            datetime object of last timestamp, or None if no data exists
        """
        session = self.get_session()
        try:
            last_record = session.query(OHLCV)\
                .filter(OHLCV.symbol == symbol, OHLCV.timeframe == timeframe)\
                .order_by(OHLCV.timestamp.desc())\
                .first()

            if last_record:
                logger.debug(f"Last saved timestamp for {symbol} {timeframe}: {last_record.timestamp}")
                return last_record.timestamp
            else:
                logger.debug(f"No existing data for {symbol} {timeframe}")
                return None
        finally:
            session.close()

    def get_ohlcv_count(self, symbol, timeframe):
        """
        Get count of OHLCV records for a symbol/timeframe

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string

        Returns:
            Number of records
        """
        session = self.get_session()
        try:
            count = session.query(OHLCV)\
                .filter(OHLCV.symbol == symbol, OHLCV.timeframe == timeframe)\
                .count()
            return count
        finally:
            session.close()


# Convenience function to initialize database
def init_database(config):
    """
    Initialize database from config

    Args:
        config: Configuration dict

    Returns:
        Database instance
    """
    db_config = config.get("database", {})
    db_type = db_config.get("type", "sqlite")

    if db_type == "sqlite":
        db_path = db_config.get("path", "./trading_data.db")
        db_url = f"sqlite:///{db_path}"
    elif db_type == "postgresql":
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 5432)
        database = db_config.get("database", "crypto_trader")
        user = db_config.get("user")
        password = db_config.get("password")
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    db = Database(db_url)
    db.create_tables()
    return db
