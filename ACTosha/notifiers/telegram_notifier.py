"""ACTosha Telegram notifier — sends formatted alerts to a Telegram chat."""

from __future__ import annotations

import os
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

__all__ = ["TelegramNotifier", "TelegramConfig"]


# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

@dataclass
class TelegramConfig:
    """Configuration for Telegram notifier.

    Attributes
    ----------
    bot_token : str
        Telegram bot token (from @BotFather). Read from TELEGRAM_BOT
        environment variable if not provided.
    chat_id : str | int
        Target chat ID. For private chats this is the user's Telegram ID.
        For channels/groups this is the channel handle or numeric ID.
    rate_limit_seconds : float
        Minimum seconds between messages to avoid spam. Default: 30.0.
    parse_mode : str
        Telegram parse mode for messages. Default: "MarkdownV2".
        Use "HTML" for HTML formatting, or None for plain text.
    """

    bot_token: str | None = None
    chat_id: str | int = 366078798
    rate_limit_seconds: float = 30.0
    parse_mode: str = "HTML"


# ------------------------------------------------------------------
# Notifier
# ------------------------------------------------------------------

class TelegramNotifier:
    """Send formatted alerts to a Telegram chat.

    Supports rate-limiting to avoid flooding the chat.

    Example
    -------
    >>> notifier = TelegramNotifier()
    >>> notifier.send_alert(
    ...     symbol="BTC/USDT:USDT",
    ...     pattern="RSI Oversold",
    ...     timeframe="1h",
    ...     strength=0.78,
    ...     entry_zone=(92000, 93000),
    ...     metadata={"rsi": 28, "volume_surge": 2.3},
    ... )
    """

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, config: TelegramConfig | None = None) -> None:
        self._config = config or TelegramConfig()

        if self._config.bot_token is None:
            token = os.environ.get("TELEGRAM_BOT", "")
            if not token:
                raise ValueError(
                    "Telegram bot token not provided and TELEGRAM_BOT "
                    "environment variable is not set."
                )
            self._config.bot_token = token

        self._last_sent: float = 0.0
        self._sent_count: int = 0
        self._error_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_alert(
        self,
        symbol: str,
        pattern: str,
        timeframe: str,
        strength: float,
        entry_zone: tuple[float, float] | list[float],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send an ACTosha opportunity alert to Telegram.

        Parameters
        ----------
        symbol : str
            Trading pair, e.g. "BTC/USDT:USDT".
        pattern : str
            Detected pattern name, e.g. "RSI Oversold", "Double Bottom".
        timeframe : str
            OHLCV timeframe, e.g. "1h", "4h".
        strength : float
            Confidence score [0.0, 1.0].
        entry_zone : tuple[float, float] | list[float]
            (lower, upper) price bounds for the entry zone.
        metadata : dict[str, Any] | None
            Additional context to include in the alert.

        Returns
        -------
        bool
            True if the message was sent successfully, False otherwise.
        """
        if not self._can_send():
            return False

        message = self._build_message(
            symbol=symbol,
            pattern=pattern,
            timeframe=timeframe,
            strength=strength,
            entry_zone=entry_zone,
            metadata=metadata,
        )

        ok = self._send_message(message)
        self._last_sent = time.monotonic()
        if ok:
            self._sent_count += 1
        else:
            self._error_count += 1
        return ok

    def send_text(self, text: str, disable_notification: bool = False) -> bool:
        """Send a plain text message to the configured chat.

        Parameters
        ----------
        text : str
            Message text. Keep under 4096 characters (Telegram limit).
        disable_notification : bool
            If True, send silently (no notification sound). Default: False.

        Returns
        -------
        bool
            True if sent successfully.
        """
        return self._send_message(text, disable_notification=disable_notification)

    @property
    def stats(self) -> dict[str, int]:
        """Return notifier statistics: sent count, error count."""
        return {
            "sent": self._sent_count,
            "errors": self._error_count,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _can_send(self) -> bool:
        """Check rate limiting — return True if message can be sent now."""
        elapsed = time.monotonic() - self._last_sent
        return elapsed >= self._config.rate_limit_seconds

    def _build_message(
        self,
        symbol: str,
        pattern: str,
        timeframe: str,
        strength: float,
        entry_zone: tuple[float, float] | list[float],
        metadata: dict[str, Any] | None,
    ) -> str:
        """Build the formatted alert message."""
        # Normalise entry_zone to (low, high)
        try:
            if len(entry_zone) == 2:
                low, high = sorted(entry_zone[:2])
            else:
                low, high = entry_zone[0], entry_zone[0]
        except Exception:
            traceback.print_exc()
            low, high = entry_zone[0], entry_zone[0]

        # Pattern-specific explanations injected after neck / break_direction
        PATTERN_EXPLANATIONS: dict[str, str] = {
            "head_shoulders": "Медвежий разворот. Цена должна упасть ниже neck для подтверждения.",
            "inverse_head_shoulders": "Бычий разворот. Цена должна подняться выше neck для подтверждения.",
            "headandshoulders": "Медвежий разворот. Цена должна упасть ниже neck для подтверждения.",
            "double_top": "Медвежий разворот. Ожидается пробой ниже neck (support) после двойной вершины.",
            "double_bottom": "Бычий разворот. Цена должна подняться выше neck (resistance) для подтверждения.",
            "ascending_triangle": "Бычий паттерн. Ожидается пробой вверх через resistance.",
            "descending_triangle": "Медвежий паттерн. Ожидается пробой вниз через support.",
            "symmetric_triangle": "Нейтральный паттерн. Ожидается сильное движение после сужения — направление пока неясно.",
            "rising_wedge": "Медвежий паттерн. Обе линии идут вверх, но сходятся — ожидается пробой вниз.",
            "falling_wedge": "Бычий паттерн. Обе линии идут вниз, но сходятся — ожидается пробой вверх.",
            "bb_squeeze": "Сжатие полос Боллинджера. Ожидается сильное движение после сжатия — вход при прорыве зоны.",
            "bb_breakout_up": "Пробой верхней полосы Боллинджера. Бычий импульс — вход при ретесте полосы.",
            "bb_breakout_down": "Пробой нижней полосы Боллинджера. Медвежий импульс — вход при ретесте полосы.",
            "rsi_oversold": "RSI ниже 30. Перекупленность — возможен отскок. Вход при развороте RSI вверх.",
            "rsi_overbought": "RSI выше 70. Перекупленность — возможен откат. Вход при развороте RSI вниз.",
            "volume_divergence_bull": "Бычья дивергенция объёма. Объём падает при росте цены — возможен откат вверх.",
            "volume_divergence_bear": "Медвежья дивергенция объёма. Объём растёт при падении цены — возможен откат вниз.",
            "volume_surge": "Всплеск объёма. Сильное движение вероятно — подтверди направление по свече.",
            "volume_surge_consecutive": "Подряд сильные свечи объёма. Тренд набирает инерцию — возможно продолжение.",
            "volume_clamp": "Объём сжат в узком диапазоне. Готовность к сильному движению — жди пробой.",
            "macd_cross_up": "MACD пересекла сигнальную линию вверх. Бычий момент — вход на подтверждении.",
            "macd_cross_down": "MACD пересекла сигнальную линию вниз. Медвежий момент — вход на подтверждении.",
            "stoch_oversold": "Стохастик ниже 20. Перекупленность — возможен отскок.",
            "stoch_overbought": "Стохастик выше 80. Перекупленность — возможен откат.",
            "bullish_engulfing": "Бычье поглощение. Медвежья свеча полностью накрыта бычьей — разворот вверх.",
            "bearish_engulfing": "Медвежье поглощение. Бычья свеча полностью накрыта медвежьей — разворот вниз.",
            "hammer": "Молот. Длинная нижняя тень — бычий сигнал при подтверждении.",
            "inverted_hammer": "Перевёрнутый молот. Длинная верхняя тень — возможен разворот вниз.",
            "doji": "Доджи (нерешительность). Рынок на перепутье — жди подтверждающую свечу.",
            "morning_star": "Утренняя звезда. Три свечи — бычий разворот. Подтверждение: закрытие выше середины первой свечи.",
            "evening_star": "Вечерняя звезда. Три свечи — медвежий разворот. Подтверждение: закрытие ниже середины первой свечи.",
        }

        # Build metadata summary line
        meta_parts: list[str] = []
        explanation_appended = False
        if metadata:
            for k, v in list(metadata.items())[:4]:
                try:
                    if isinstance(v, float):
                        meta_parts.append(f"{k}={v:.2f}")
                    else:
                        meta_parts.append(f"{k}={v}")
                except Exception:
                    meta_parts.append(f"{k}={str(v)}")

        # Append explanation after neck= or break_direction= lines
        explanation = PATTERN_EXPLANATIONS.get(pattern, "")
        if explanation:
            enriched_parts: list[str] = []
            for part in meta_parts:
                enriched_parts.append(part)
                if ("neck=" in part or "break_direction=" in part) and not explanation_appended:
                    enriched_parts.append(f"\u2192 {explanation}")
                    explanation_appended = True
            meta_summary = " | ".join(enriched_parts)
        else:
            meta_summary = " | ".join(meta_parts) if meta_parts else ""

        # Main alert block
        lines = [
            "🔔 <b>ACTosha Alert</b>",
            f"<b>{self._escape(pattern)} on {symbol}</b>",
            f"⏱ Timeframe: <b>{timeframe}</b>",
            f"📊 Strength: <b>{strength:.2f}</b>/1.0",
            f"🎯 Entry zone: <code>{low:.4f}</code> – <code>{high:.4f}</code>",
        ]
        if meta_summary:
            lines.append(f"📐 {meta_summary}")

        return "\n".join(lines)

    def _send_message(
        self,
        text: str,
        disable_notification: bool = False,
    ) -> bool:
        """POST the message to the Telegram Bot API."""
        url = self.BASE_URL.format(token=self._config.bot_token)
        payload = {
            "chat_id": self._config.chat_id,
            "text": text,
            "parse_mode": self._config.parse_mode if self._config.parse_mode else None,
            "disable_notification": disable_notification,
        }
        # Remove None parse_mode
        if payload["parse_mode"] is None:
            del payload["parse_mode"]

        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception:
            traceback.print_exc()
            return False

    @staticmethod
    def _escape(text: str) -> str:
        """Escape characters problematic for Telegram HTML."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")