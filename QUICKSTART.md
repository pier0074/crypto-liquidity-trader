# Quick Start Guide

Get up and running with Crypto Liquidity Trader in minutes!

## Prerequisites

- Python 3.9 or higher
- Git

## Installation

### 1. Navigate to Project Directory

```bash
cd crypto-liquidity-trader
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Settings

```bash
# config.yaml is already created, edit it with your preferences
nano config.yaml  # or use any text editor
```

**Important Configuration Items:**

- **Email Notifications** (optional): Edit the `notifications.email` section
  ```yaml
  notifications:
    email:
      enabled: true
      smtp_server: smtp.gmail.com
      smtp_port: 587
      sender_email: your_email@gmail.com
      sender_password: your_app_password
      recipient_email: your_email@gmail.com
  ```

- **Trading Pairs**: Edit `trading_pairs` list or leave empty to auto-fetch top 50 by volume

- **Risk Management**: Adjust `risk_management` settings for your account size

## Usage

### Step 1: Fetch Historical Data

First, download historical market data:

```bash
python scripts/fetch_historical.py
```

This will:
- Fetch 1-minute OHLCV data for configured pairs
- Aggregate to higher timeframes (5m, 15m, 1h, 4h, 1d)
- Store everything in SQLite database

**Note**: This may take 10-30 minutes depending on the number of pairs and date range.

### Step 2: Run Pattern Scanner

Run the scanner to detect patterns and generate signals:

```bash
# Single scan
python scripts/run_scanner.py --once

# Continuous scanning (recommended)
python scripts/run_scanner.py
```

The scanner will:
- Analyze all symbols and timeframes
- Detect Fair Value Gaps (imbalances)
- Generate trading signals with entry/TP/SL levels
- Send email notifications for new signals
- Update every 60 seconds (configurable)

### Step 3: Start Web Dashboard

Open a new terminal and start the web interface:

```bash
source venv/bin/activate  # If not already activated
python src/web/app.py
```

Then open your browser to: **http://127.0.0.1:5000**

The dashboard shows:
- Active trading signals
- Pattern detection summary across all symbols/timeframes
- Interactive price charts with patterns highlighted
- Real-time statistics

### Step 4 (Optional): Run Backtesting

Test the strategy on historical data:

```bash
python scripts/backtest.py
```

This will show you:
- Total return and win rate
- Profit factor and max drawdown
- Individual trade details

## Email Notifications

To enable email notifications:

1. **Gmail Users**: Use an [App Password](https://support.google.com/accounts/answer/185833)
   - Go to Google Account → Security → 2-Step Verification → App Passwords
   - Generate a password for "Mail"
   - Use this password in `config.yaml`

2. **Other Providers**: Update SMTP server and port in config

3. **Test Email Setup**:
   ```python
   from src.notifications.email_notifier import EmailNotifier
   from src.utils import load_config

   config = load_config()
   notifier = EmailNotifier(config)
   notifier.send_test_email()
   ```

## Configuration Tips

### Adjust Pattern Detection Sensitivity

In `config.yaml`:

```yaml
patterns:
  fair_value_gap:
    min_gap_percentage: 0.1  # Lower = more patterns detected
    lookback_candles: 100     # How many recent candles to analyze
```

### Adjust Risk/Reward Requirements

```yaml
signals:
  min_risk_reward: 2.0  # Minimum R/R to generate signal (2:1, 3:1, etc.)
  take_profit_levels: [2, 3, 4]  # Multiple TP levels
```

### Change Scan Interval

```yaml
scanner:
  scan_interval_seconds: 60  # How often to scan (default: 60s)
```

## Typical Workflow

### For Manual Trading:

1. **Morning**: Start scanner in continuous mode
2. **Throughout Day**: Receive email notifications for new signals
3. **Review**: Check web dashboard for signal details and charts
4. **Execute**: Manually place limit orders based on signals
5. **Monitor**: Track positions and adjust as needed

### For Monitoring Only:

1. Run scanner once per hour via cron job
2. Review dashboard when available
3. Use signals as confluence with your own analysis

## Common Issues

### "No data available" in dashboard

**Solution**: Run `python scripts/fetch_historical.py` first

### Scanner not detecting patterns

**Reasons**:
- Insufficient historical data
- `min_gap_percentage` too high
- No imbalances in recent data (normal in ranging markets)

**Solution**: Lower `min_gap_percentage` to 0.05 or wait for more volatile market conditions

### Email notifications not working

**Solution**:
- Verify SMTP credentials
- Check that email is enabled in config
- Test with `notifier.send_test_email()`
- Check spam folder

## Next Steps

- **Add More Patterns**: Extend `src/patterns/` with Liquidity Sweeps, Order Blocks, etc.
- **Integrate Exchange API**: Add KuCoin API keys for automated order placement
- **Optimize Parameters**: Backtest different settings to find optimal configuration
- **Deploy to VPS**: Run 24/7 on a cloud server for continuous monitoring

## Support

For issues or questions, check the main README.md or create an issue on GitHub.

Happy Trading!
