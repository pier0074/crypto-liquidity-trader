"""
Email notification system for sending trading signals
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Sends email notifications for trading signals"""

    def __init__(self, config):
        """
        Initialize email notifier

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.email_config = config.get("notifications", {}).get("email", {})

        self.enabled = self.email_config.get("enabled", False)
        self.smtp_server = self.email_config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = self.email_config.get("smtp_port", 587)
        self.sender_email = self.email_config.get("sender_email")
        self.sender_password = self.email_config.get("sender_password")
        self.recipient_email = self.email_config.get("recipient_email")

        if self.enabled:
            self._validate_config()
            logger.info(f"Email notifications enabled: {self.sender_email} -> {self.recipient_email}")
        else:
            logger.info("Email notifications disabled")

    def _validate_config(self):
        """Validate email configuration"""
        if not self.sender_email:
            raise ValueError("Email sender_email not configured")
        if not self.sender_password:
            raise ValueError("Email sender_password not configured")
        if not self.recipient_email:
            raise ValueError("Email recipient_email not configured")

    def send_signal_notification(self, signal, message_body):
        """
        Send email notification for a trading signal

        Args:
            signal: Signal dictionary
            message_body: Formatted message body

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Email notifications disabled, skipping")
            return False

        try:
            # Create message
            subject = f"🚨 Trading Signal: {signal['direction'].upper()} {signal['symbol']} ({signal['timeframe']})"

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = self.recipient_email
            msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

            # Create plain text and HTML versions
            text_part = MIMEText(message_body, "plain")
            html_part = MIMEText(self._format_html(signal, message_body), "html")

            msg.attach(text_part)
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Email notification sent for {signal['symbol']} {signal['direction']}")
            return True

        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False

    def send_summary_notification(self, summary_data):
        """
        Send daily/periodic summary email

        Args:
            summary_data: Dictionary with summary information

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            subject = f"📊 Trading Summary - {datetime.utcnow().strftime('%Y-%m-%d')}"

            # Create message body
            body = self._format_summary(summary_data)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = self.recipient_email

            text_part = MIMEText(body, "plain")
            msg.attach(text_part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info("Summary email sent")
            return True

        except Exception as e:
            logger.error(f"Error sending summary email: {e}")
            return False

    def send_test_email(self):
        """
        Send test email to verify configuration

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning("Email notifications disabled, cannot send test email")
            return False

        try:
            subject = "✅ Crypto Liquidity Trader - Test Email"
            body = """
This is a test email from your Crypto Liquidity Trader system.

If you receive this email, your email notifications are configured correctly!

System Information:
- SMTP Server: {smtp_server}
- SMTP Port: {smtp_port}
- Sender: {sender}
- Recipient: {recipient}
- Timestamp: {timestamp}

Happy Trading!
            """.format(
                smtp_server=self.smtp_server,
                smtp_port=self.smtp_port,
                sender=self.sender_email,
                recipient=self.recipient_email,
                timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            )

            msg = MIMEText(body, "plain")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = self.recipient_email

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info("Test email sent successfully")
            return True

        except Exception as e:
            logger.error(f"Error sending test email: {e}")
            return False

    def _format_html(self, signal, text_body):
        """
        Format signal as HTML email

        Args:
            signal: Signal dictionary
            text_body: Plain text body

        Returns:
            HTML string
        """
        direction_color = "#2ecc71" if signal["direction"] == "long" else "#e74c3c"
        direction_emoji = "📈" if signal["direction"] == "long" else "📉"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: {direction_color};
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f9f9f9;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 0 0 5px 5px;
        }}
        .signal-info {{
            background-color: white;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 4px solid {direction_color};
        }}
        .price {{
            font-size: 18px;
            font-weight: bold;
            color: {direction_color};
        }}
        .label {{
            font-weight: bold;
            color: #666;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{direction_emoji} NEW TRADING SIGNAL</h1>
            <h2>{signal['symbol']} - {signal['direction'].upper()}</h2>
        </div>
        <div class="content">
            <div class="signal-info">
                <p><span class="label">Timeframe:</span> {signal['timeframe']}</p>
                <p><span class="label">Entry Price:</span> <span class="price">{signal['entry_price']:.8f}</span></p>
                <p><span class="label">Stop Loss:</span> {signal['stop_loss']:.8f}</p>
                <p><span class="label">Take Profit 1:</span> {signal['take_profit_1']:.8f}</p>
"""
        if signal.get('take_profit_2'):
            html += f"                <p><span class=\"label\">Take Profit 2:</span> {signal['take_profit_2']:.8f}</p>\n"
        if signal.get('take_profit_3'):
            html += f"                <p><span class=\"label\">Take Profit 3:</span> {signal['take_profit_3']:.8f}</p>\n"

        html += f"""
                <p><span class="label">Risk/Reward:</span> {signal['risk_reward_ratio']:.2f}:1</p>
                <p><span class="label">Position Size:</span> {signal['position_size']:.4f} {signal['symbol'].split('/')[0]}</p>
                <p><span class="label">Risk Amount:</span> ${signal['risk_amount']:.2f}</p>
            </div>
            <p><strong>Notes:</strong> {signal.get('notes', '')}</p>
            <p><strong>Valid Until:</strong> {signal.get('valid_until', 'N/A')}</p>
        </div>
        <div class="footer">
            <p>Crypto Liquidity Trader - Automated Signal Generation</p>
            <p>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _format_summary(self, summary_data):
        """
        Format summary data as text

        Args:
            summary_data: Summary dictionary

        Returns:
            Formatted string
        """
        body = f"""
TRADING SUMMARY - {datetime.utcnow().strftime('%Y-%m-%d')}

ACTIVE SIGNALS: {summary_data.get('total_signals', 0)}
  Long: {summary_data.get('long_signals', 0)}
  Short: {summary_data.get('short_signals', 0)}

DETECTED PATTERNS: {summary_data.get('total_patterns', 0)}

TOP OPPORTUNITIES:
"""
        for symbol, data in summary_data.get('top_opportunities', {}).items():
            body += f"  {symbol}: {data.get('pattern_count', 0)} patterns\n"

        body += f"""
TOTAL RISK: ${summary_data.get('total_risk', 0):.2f}

Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        return body
