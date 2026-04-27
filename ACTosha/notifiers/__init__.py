"""ACTosha notifiers — alert delivery to external channels.

Currently supported:
    Telegram — formatted opportunity alerts via Bot API

Usage::

    from ACTosha.notifiers import TelegramNotifier

    notifier = TelegramNotifier()
    notifier.send_alert(
        symbol="BTC/USDT:USDT",
        pattern="RSI Oversold",
        timeframe="1h",
        strength=0.78,
        entry_zone=(92000, 93000),
        metadata={"rsi": 28},
    )
"""

from ACTosha.notifiers.telegram_notifier import TelegramConfig, TelegramNotifier

__all__ = ["TelegramNotifier", "TelegramConfig"]