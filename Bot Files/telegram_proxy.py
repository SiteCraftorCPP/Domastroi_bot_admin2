"""Нормализация TELEGRAM_PROXY для aiogram (HTTP/SOCKS5, формат host:port:user:pass)."""
from __future__ import annotations

from typing import Optional
from urllib.parse import quote


def normalize_telegram_proxy(raw: Optional[str]) -> Optional[str]:
    """
    Поддержка:
    - socks5://user:pass@host:port (или http://...)
    - host:port:user:pass (как в панелях прокси)
    """
    s = (raw or "").strip()
    if not s:
        return None
    if "://" in s:
        return s
    parts = s.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"socks5://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    return s
