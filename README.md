# Crypto Liquidity Trader

A sophisticated crypto trading system that identifies liquidity-based patterns (Fair Value Gaps, Liquidity Sweeps, Order Blocks) and generates high R/R trade setups with automated notifications.

## Features

- **Multi-Timeframe Analysis**: Analyzes 1m, 5m, 15m, 1H, 4H, 1D timeframes simultaneously
- **Pattern Detection**: Fair Value Gaps (Imbalances), with extensible architecture for more patterns
- **Smart Signal Generation**: Calculates Risk/Reward ratios and generates trade setups
- **Email Notifications**: Sends detailed trade alerts with entry, TP, and SL levels
- **Backtesting Engine**: Test strategies on historical data
- **Web Dashboard**: Visual interface showing candles and trade opportunities across all symbols
- **Top Crypto Coverage**: Monitors top 20-50 most liquid cryptocurrencies
- **Scalable Architecture**: Designed for future automated trading integration

## Tech Stack

- **Python 3.9+**
- **CCXT**: Exchange API integration (KuCoin)
- **Pandas**: Data manipulation and analysis
- **SQLite**: Local database (upgradeable to PostgreSQL)
- **Flask**: Web dashboard
- **Plotly**: Interactive charts

## Installation

1. Clone the repository:
```bash
git clone <repo-url>
cd crypto-liquidity-trader
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure settings:
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

## Configuration

Edit `config.yaml` to set:
- Exchange API credentials (optional for public data)
- Email notification settings
- Trading pairs to monitor
- Risk management parameters
- Pattern detection settings

## Usage

### Fetch Historical Data
```bash
python scripts/fetch_historical.py
```

### Run Pattern Scanner
```bash
python scripts/run_scanner.py
```

### Run Backtesting
```bash
python scripts/backtest.py
```

### Start Web Dashboard
```bash
python src/web/app.py
```

## Project Structure

```
crypto-liquidity-trader/
├── src/
│   ├── data/           # Data collection and storage
│   ├── patterns/       # Pattern detection algorithms
│   ├── signals/        # Signal generation and R/R calculation
│   ├── notifications/  # Email and alert system
│   ├── backtesting/    # Backtesting engine
│   └── web/            # Web dashboard
├── scripts/            # Utility scripts
└── tests/              # Unit tests
```

## Patterns Implemented

### Fair Value Gap (FVG) / Imbalance
Detects areas where price moved rapidly with minimal trading, creating an imbalance that price often returns to fill.

**Detection Criteria**:
- Three consecutive candles
- Gap between candle 1 high/low and candle 3 low/high
- Middle candle shows strong directional movement

**More patterns coming soon**: Liquidity Sweeps, Order Blocks, Breaker Blocks, etc.

## Roadmap

- [x] Project setup and architecture
- [ ] Data collection from KuCoin
- [ ] Fair Value Gap detection
- [ ] Signal generation with R/R
- [ ] Email notifications
- [ ] Backtesting engine
- [ ] Web dashboard
- [ ] Additional patterns (Liquidity Sweeps, Order Blocks)
- [ ] Automated trading via API

## Contributing

This is a private trading system. Please follow best practices:
- Write clean, documented code
- Add tests for new features
- Commit frequently with clear messages

## License

Private - All Rights Reserved
