"""
Backtesting engine for testing trading strategies on historical data
"""
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Backtesting engine for evaluating trading strategies"""

    def __init__(self, config):
        """
        Initialize backtest engine

        Args:
            config: Configuration dictionary
        """
        self.config = config
        backtest_config = config.get("backtesting", {})

        self.initial_capital = backtest_config.get("initial_capital", 10000)
        self.commission_percent = backtest_config.get("commission_percent", 0.1)
        self.slippage_percent = backtest_config.get("slippage_percent", 0.05)

        # State
        self.capital = self.initial_capital
        self.positions = []
        self.closed_trades = []
        self.equity_curve = []

    def reset(self):
        """Reset backtest state"""
        self.capital = self.initial_capital
        self.positions = []
        self.closed_trades = []
        self.equity_curve = []

    def run_backtest(self, signals, ohlcv_data):
        """
        Run backtest on signals with historical data

        Args:
            signals: List of signal dictionaries
            ohlcv_data: Dictionary mapping (symbol, timeframe) to OHLCV DataFrame

        Returns:
            Backtest results dictionary
        """
        self.reset()

        logger.info(f"Running backtest with {len(signals)} signals")
        logger.info(f"Initial capital: ${self.initial_capital:,.2f}")

        # Sort signals by timestamp
        signals_sorted = sorted(signals, key=lambda x: x.get("generated_at", datetime.min))

        # Process each signal
        for signal in signals_sorted:
            self._process_signal(signal, ohlcv_data)

        # Calculate results
        results = self._calculate_results()

        logger.info("Backtest completed")
        logger.info(f"Final capital: ${self.capital:,.2f}")
        logger.info(f"Total return: {results['total_return_percent']:.2f}%")
        logger.info(f"Win rate: {results['win_rate']:.2f}%")

        return results

    def _process_signal(self, signal, ohlcv_data):
        """
        Process a single signal and simulate trade execution

        Args:
            signal: Signal dictionary
            ohlcv_data: OHLCV data dictionary
        """
        symbol = signal["symbol"]
        timeframe = signal["timeframe"]
        direction = signal["direction"]
        entry_price = signal["entry_price"]
        stop_loss = signal["stop_loss"]
        take_profit_1 = signal["take_profit_1"]

        # Get historical data for this symbol/timeframe
        key = (symbol, timeframe)
        if key not in ohlcv_data:
            logger.warning(f"No OHLCV data for {symbol} {timeframe}")
            return

        df = ohlcv_data[key]

        # Find entry point in historical data
        signal_time = signal.get("generated_at", datetime.utcnow())
        df_after = df[df["timestamp"] >= signal_time]

        if len(df_after) < 2:
            return

        # Apply slippage to entry
        entry_price_actual = self._apply_slippage(entry_price, direction)

        # Calculate position size based on risk
        risk_amount = signal.get("risk_amount", self.capital * 0.01)
        position_size = signal.get("position_size", 1)

        # Calculate entry cost with commission
        entry_cost = position_size * entry_price_actual
        commission = entry_cost * (self.commission_percent / 100)
        total_entry_cost = entry_cost + commission

        if total_entry_cost > self.capital:
            logger.debug(f"Insufficient capital for {symbol} signal")
            return

        # Deduct capital
        self.capital -= total_entry_cost

        # Track position
        position = {
            "signal": signal,
            "entry_price": entry_price_actual,
            "position_size": position_size,
            "direction": direction,
            "entry_time": df_after.iloc[0]["timestamp"],
            "stop_loss": stop_loss,
            "take_profit": take_profit_1,
        }

        # Simulate trade over subsequent candles
        exit_info = None
        for i in range(1, len(df_after)):
            candle = df_after.iloc[i]
            exit_info = self._check_exit(position, candle)
            if exit_info:
                break

        if exit_info:
            self._close_position(position, exit_info)
        else:
            # Position didn't close in available data
            logger.debug(f"Position {symbol} did not close in available data")

    def _check_exit(self, position, candle):
        """
        Check if position should exit based on candle

        Args:
            position: Position dictionary
            candle: Current candle data

        Returns:
            Exit info dict or None
        """
        direction = position["direction"]
        stop_loss = position["stop_loss"]
        take_profit = position["take_profit"]

        if direction == "long":
            # Check stop loss
            if candle["low"] <= stop_loss:
                return {
                    "exit_price": stop_loss,
                    "exit_time": candle["timestamp"],
                    "exit_reason": "stop_loss"
                }
            # Check take profit
            if candle["high"] >= take_profit:
                return {
                    "exit_price": take_profit,
                    "exit_time": candle["timestamp"],
                    "exit_reason": "take_profit"
                }
        else:  # short
            # Check stop loss
            if candle["high"] >= stop_loss:
                return {
                    "exit_price": stop_loss,
                    "exit_time": candle["timestamp"],
                    "exit_reason": "stop_loss"
                }
            # Check take profit
            if candle["low"] <= take_profit:
                return {
                    "exit_price": take_profit,
                    "exit_time": candle["timestamp"],
                    "exit_reason": "take_profit"
                }

        return None

    def _close_position(self, position, exit_info):
        """
        Close a position and update capital

        Args:
            position: Position dictionary
            exit_info: Exit information dictionary
        """
        direction = position["direction"]
        entry_price = position["entry_price"]
        exit_price = exit_info["exit_price"]
        position_size = position["position_size"]

        # Apply slippage to exit
        exit_price_actual = self._apply_slippage(exit_price, direction, is_exit=True)

        # Calculate P/L
        if direction == "long":
            pnl = (exit_price_actual - entry_price) * position_size
        else:  # short
            pnl = (entry_price - exit_price_actual) * position_size

        # Apply commission
        exit_cost = position_size * exit_price_actual
        commission = exit_cost * (self.commission_percent / 100)
        pnl -= commission

        # Update capital
        exit_value = exit_cost
        self.capital += exit_value

        # Record trade
        trade = {
            "symbol": position["signal"]["symbol"],
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price_actual,
            "entry_time": position["entry_time"],
            "exit_time": exit_info["exit_time"],
            "exit_reason": exit_info["exit_reason"],
            "position_size": position_size,
            "pnl": pnl,
            "pnl_percent": (pnl / (position_size * entry_price)) * 100,
        }

        self.closed_trades.append(trade)

        # Record equity
        self.equity_curve.append({
            "timestamp": exit_info["exit_time"],
            "equity": self.capital + pnl
        })

        logger.debug(f"Closed {direction} {trade['symbol']} - P/L: ${pnl:.2f} ({trade['pnl_percent']:.2f}%)")

    def _apply_slippage(self, price, direction, is_exit=False):
        """
        Apply slippage to price

        Args:
            price: Original price
            direction: Trade direction
            is_exit: Whether this is an exit (reverses slippage direction)

        Returns:
            Price with slippage applied
        """
        slippage = price * (self.slippage_percent / 100)

        if direction == "long":
            return price + slippage if not is_exit else price - slippage
        else:  # short
            return price - slippage if not is_exit else price + slippage

    def _calculate_results(self):
        """
        Calculate backtest results

        Returns:
            Results dictionary
        """
        if not self.closed_trades:
            return {
                "total_return": 0,
                "total_return_percent": 0,
                "win_rate": 0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
            }

        # Basic stats
        total_trades = len(self.closed_trades)
        winning_trades = [t for t in self.closed_trades if t["pnl"] > 0]
        losing_trades = [t for t in self.closed_trades if t["pnl"] <= 0]

        total_wins = len(winning_trades)
        total_losses = len(losing_trades)

        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

        # P/L stats
        total_return = self.capital - self.initial_capital
        total_return_percent = (total_return / self.initial_capital) * 100

        avg_win = sum(t["pnl"] for t in winning_trades) / total_wins if total_wins > 0 else 0
        avg_loss = sum(t["pnl"] for t in losing_trades) / total_losses if total_losses > 0 else 0

        total_win_amount = sum(t["pnl"] for t in winning_trades)
        total_loss_amount = abs(sum(t["pnl"] for t in losing_trades))

        profit_factor = total_win_amount / total_loss_amount if total_loss_amount > 0 else 0

        # Drawdown
        max_drawdown = self._calculate_max_drawdown()

        results = {
            "initial_capital": self.initial_capital,
            "final_capital": self.capital,
            "total_return": total_return,
            "total_return_percent": total_return_percent,
            "total_trades": total_trades,
            "winning_trades": total_wins,
            "losing_trades": total_losses,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "trades": self.closed_trades,
            "equity_curve": self.equity_curve,
        }

        return results

    def _calculate_max_drawdown(self):
        """
        Calculate maximum drawdown

        Returns:
            Max drawdown percentage
        """
        if not self.equity_curve:
            return 0

        equity = [e["equity"] for e in self.equity_curve]
        peak = equity[0]
        max_dd = 0

        for value in equity:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def print_summary(self, results):
        """
        Print backtest summary

        Args:
            results: Results dictionary
        """
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Initial Capital:    ${results['initial_capital']:,.2f}")
        print(f"Final Capital:      ${results['final_capital']:,.2f}")
        print(f"Total Return:       ${results['total_return']:,.2f} ({results['total_return_percent']:.2f}%)")
        print(f"\nTotal Trades:       {results['total_trades']}")
        print(f"Winning Trades:     {results['winning_trades']} ({results['win_rate']:.2f}%)")
        print(f"Losing Trades:      {results['losing_trades']}")
        print(f"\nAverage Win:        ${results['avg_win']:.2f}")
        print(f"Average Loss:       ${results['avg_loss']:.2f}")
        print(f"Profit Factor:      {results['profit_factor']:.2f}")
        print(f"Max Drawdown:       {results['max_drawdown']:.2f}%")
        print("=" * 60)
