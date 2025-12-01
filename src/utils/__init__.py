"""
Utility functions and modules for the trading system
"""
import yaml
import logging
import colorlog
from pathlib import Path

# Import chart analysis functions
from .chart_analysis import (
    find_swing_points,
    find_equal_levels,
    find_round_numbers,
    find_volume_clusters,
    calculate_dynamic_take_profits
)


def load_config(config_path="config.yaml"):
    """Load configuration from YAML file"""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    return config


def setup_logging(config=None):
    """Setup logging with colors and formatting"""
    if config is None:
        log_level = "INFO"
        log_file = None
        console = True
    else:
        log_config = config.get("logging", {})
        log_level = log_config.get("level", "INFO")
        log_file = log_config.get("file")
        console = log_config.get("console", True)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

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

    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers = []

    if console:
        console_handler = colorlog.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def timeframe_to_minutes(timeframe):
    """Convert timeframe string to minutes"""
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
    """Convert minutes to timeframe string"""
    if minutes < 60:
        return f"{minutes}m"
    elif minutes < 1440:
        return f"{minutes // 60}h"
    elif minutes < 10080:
        return f"{minutes // 1440}d"
    else:
        return f"{minutes // 10080}w"


def calculate_position_size(entry_price, stop_loss, risk_amount):
    """Calculate position size based on risk amount"""
    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit == 0:
        return 0
    return risk_amount / risk_per_unit


def calculate_risk_reward(entry_price, stop_loss, take_profit):
    """Calculate risk/reward ratio"""
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    if risk == 0:
        return 0
    return reward / risk


def format_price(price, decimals=8):
    """Format price with appropriate decimals"""
    formatted = f"{price:.{decimals}f}".rstrip("0").rstrip(".")
    return formatted


__all__ = [
    'load_config',
    'setup_logging',
    'timeframe_to_minutes',
    'minutes_to_timeframe',
    'calculate_position_size',
    'calculate_risk_reward',
    'format_price',
    'find_swing_points',
    'find_equal_levels',
    'find_round_numbers',
    'find_volume_clusters',
    'calculate_dynamic_take_profits',
]
