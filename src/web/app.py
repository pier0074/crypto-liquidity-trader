#!/usr/bin/env python3
"""
Web dashboard for monitoring trading signals and patterns
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from src.utils import load_config, setup_logging
from src.data.database import init_database
from src.data.collector import DataCollector
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
import json
import logging

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load configuration
config = load_config()
setup_logging(config)

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


@app.route("/")
def index():
    """Main dashboard page"""
    return render_template("index.html")


@app.route("/api/signals/active")
def get_active_signals():
    """Get all active trading signals"""
    try:
        signals = db.get_active_signals()

        signals_data = []
        for signal in signals:
            signals_data.append({
                "id": signal.id,
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "direction": signal.direction,
                "entry_price": float(signal.entry_price),
                "stop_loss": float(signal.stop_loss),
                "take_profit_1": float(signal.take_profit_1),
                "risk_reward_ratio": float(signal.risk_reward_ratio),
                "generated_at": signal.generated_at.isoformat() if signal.generated_at else None,
                "status": signal.status,
            })

        return jsonify({
            "success": True,
            "signals": signals_data,
            "count": len(signals_data)
        })

    except Exception as e:
        logger.error(f"Error getting active signals: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/patterns/summary")
def get_patterns_summary():
    """Get summary of detected patterns across all symbols/timeframes"""
    try:
        session = db.get_session()

        from src.data.database import Pattern
        from sqlalchemy import func

        # Get pattern counts by symbol and timeframe
        results = session.query(
            Pattern.symbol,
            Pattern.timeframe,
            Pattern.pattern_type,
            Pattern.direction,
            func.count(Pattern.id).label("count")
        ).filter(
            Pattern.is_filled == False
        ).group_by(
            Pattern.symbol,
            Pattern.timeframe,
            Pattern.pattern_type,
            Pattern.direction
        ).all()

        session.close()

        # Organize data
        summary = {}
        for row in results:
            symbol = row.symbol
            if symbol not in summary:
                summary[symbol] = {}

            timeframe = row.timeframe
            if timeframe not in summary[symbol]:
                summary[symbol][timeframe] = {
                    "total": 0,
                    "bullish": 0,
                    "bearish": 0,
                    "patterns": []
                }

            summary[symbol][timeframe]["total"] += row.count
            if row.direction == "bullish":
                summary[symbol][timeframe]["bullish"] += row.count
            else:
                summary[symbol][timeframe]["bearish"] += row.count

            summary[symbol][timeframe]["patterns"].append({
                "type": row.pattern_type,
                "direction": row.direction,
                "count": row.count
            })

        return jsonify({
            "success": True,
            "summary": summary
        })

    except Exception as e:
        logger.error(f"Error getting patterns summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chart/<symbol>/<timeframe>")
def get_chart_data(symbol, timeframe):
    """Get chart data for a symbol/timeframe with patterns marked"""
    try:
        from datetime import datetime, timedelta

        # Get OHLCV data
        start_time = datetime.utcnow() - timedelta(hours=24)
        ohlcv_records = db.get_ohlcv(symbol, timeframe, start_time=start_time, limit=500)

        if not ohlcv_records:
            return jsonify({
                "success": False,
                "error": "No data available for this symbol/timeframe"
            }), 404

        # Convert to DataFrame
        df = pd.DataFrame([{
            "timestamp": r.timestamp,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume
        } for r in ohlcv_records])

        # Create candlestick chart
        fig = go.Figure(data=[
            go.Candlestick(
                x=df["timestamp"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="Price"
            )
        ])

        # Get patterns for this symbol/timeframe
        session = db.get_session()
        from src.data.database import Pattern

        patterns = session.query(Pattern).filter(
            Pattern.symbol == symbol,
            Pattern.timeframe == timeframe,
            Pattern.is_filled == False
        ).all()

        session.close()

        # Add pattern zones to chart
        for pattern in patterns:
            color = "rgba(0, 255, 0, 0.2)" if pattern.direction == "bullish" else "rgba(255, 0, 0, 0.2)"
            fig.add_shape(
                type="rect",
                x0=pattern.start_timestamp,
                x1=pattern.end_timestamp,
                y0=pattern.price_low,
                y1=pattern.price_high,
                fillcolor=color,
                line=dict(width=0),
                name=f"{pattern.pattern_type} {pattern.direction}"
            )

        fig.update_layout(
            title=f"{symbol} {timeframe}",
            xaxis_title="Time",
            yaxis_title="Price",
            height=600,
            xaxis_rangeslider_visible=False
        )

        return jsonify({
            "success": True,
            "chart": json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig))
        })

    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/symbols")
def get_symbols():
    """Get list of available symbols"""
    try:
        symbols = config.get("trading_pairs", [])
        if not symbols:
            # Get from database
            session = db.get_session()
            from src.data.database import OHLCV
            from sqlalchemy import distinct

            symbols = [s[0] for s in session.query(distinct(OHLCV.symbol)).all()]
            session.close()

        return jsonify({
            "success": True,
            "symbols": symbols
        })

    except Exception as e:
        logger.error(f"Error getting symbols: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats")
def get_stats():
    """Get overall statistics"""
    try:
        session = db.get_session()

        from src.data.database import Pattern, Signal, OHLCV
        from sqlalchemy import func

        # Get counts
        total_patterns = session.query(func.count(Pattern.id)).filter(Pattern.is_filled == False).scalar()
        total_signals = session.query(func.count(Signal.id)).filter(Signal.status == "pending").scalar()
        total_symbols = session.query(func.count(func.distinct(OHLCV.symbol))).scalar()

        # Get signal breakdown
        long_signals = session.query(func.count(Signal.id)).filter(
            Signal.status == "pending",
            Signal.direction == "long"
        ).scalar()

        short_signals = session.query(func.count(Signal.id)).filter(
            Signal.status == "pending",
            Signal.direction == "short"
        ).scalar()

        session.close()

        return jsonify({
            "success": True,
            "stats": {
                "total_patterns": total_patterns or 0,
                "total_signals": total_signals or 0,
                "total_symbols": total_symbols or 0,
                "long_signals": long_signals or 0,
                "short_signals": short_signals or 0,
            }
        })

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def main():
    """Run the web application"""
    web_config = config.get("web", {})
    host = web_config.get("host", "127.0.0.1")
    port = web_config.get("port", 5000)
    debug = web_config.get("debug", True)

    logger.info("=" * 60)
    logger.info("Starting Web Dashboard")
    logger.info(f"URL: http://{host}:{port}")
    logger.info("=" * 60)

    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
