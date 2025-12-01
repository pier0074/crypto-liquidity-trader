"""
Utility functions for the trading system
"""
import yaml
import logging
import colorlog
from pathlib import Path


def load_config(config_path="config.yaml"):
    """
    Load configuration from YAML file

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    return config


def setup_logging(config=None):
    """
    Setup logging with colors and formatting

    Args:
        config: Configuration dict (optional)
    """
    if config is None:
        log_level = "INFO"
        log_file = None
        console = True
    else:
        log_config = config.get("logging", {})
        log_level = log_config.get("level", "INFO")
        log_file = log_config.get("file")
        console = log_config.get("console", True)

    # Create logs directory if needed
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Setup color formatter for console
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s%(reset)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )

    # Setup file formatter
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Add console handler
    if console:
        console_handler = colorlog.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def timeframe_to_minutes(timeframe):
    """
    Convert timeframe string to minutes

    Args:
        timeframe: Timeframe string (e.g., '1m', '5m', '1h', '1d')

    Returns:
        Number of minutes as integer
    """
    unit = timeframe[-1]
    value = int(timeframe[:-1])

    if unit == "m":
        return value
    elif unit == "h":
        return value * 60
    elif unit == "d":
        return value * 60 * 24
    elif unit == "w":
        return value * 60 * 24 * 7
    else:
        raise ValueError(f"Unknown timeframe unit: {unit}")


def minutes_to_timeframe(minutes):
    """
    Convert minutes to timeframe string

    Args:
        minutes: Number of minutes

    Returns:
        Timeframe string
    """
    if minutes < 60:
        return f"{minutes}m"
    elif minutes < 1440:
        return f"{minutes // 60}h"
    elif minutes < 10080:
        return f"{minutes // 1440}d"
    else:
        return f"{minutes // 10080}w"


def calculate_position_size(entry_price, stop_loss, risk_amount):
    """
    Calculate position size based on risk amount

    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
        risk_amount: Amount to risk in USD

    Returns:
        Position size
    """
    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit == 0:
        return 0
    return risk_amount / risk_per_unit


def calculate_risk_reward(entry_price, stop_loss, take_profit):
    """
    Calculate risk/reward ratio

    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
        take_profit: Take profit price

    Returns:
        Risk/reward ratio
    """
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)

    if risk == 0:
        return 0

    return reward / risk


def format_price(price, decimals=8):
    """
    Format price with appropriate decimals

    Args:
        price: Price value
        decimals: Maximum decimal places

    Returns:
        Formatted price string
    """
    # Remove trailing zeros
    formatted = f"{price:.{decimals}f}".rstrip("0").rstrip(".")
    return formatted
