"""Утилиты для форматирования текстовых ответов."""

from __future__ import annotations

import re


TAG_PATTERN = re.compile(r"<[^>]+>")


def strip_html_tags(text: str) -> str:
    """
    Удаляет HTML теги и базовые сущности.

    Args:
        text: Исходная строка с HTML тегами.

    Returns:
        Строка без HTML.
    """
    clean = TAG_PATTERN.sub("", text)
    clean = (
        clean.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return clean.strip()


def format_for_telegram(text: str) -> str:
    """Оставляет HTML форматирование для Telegram."""
    return text


def format_for_avito(text: str) -> str:
    """Удаляет HTML форматирование, совместимое с Avito Messenger."""
    return strip_html_tags(text)
