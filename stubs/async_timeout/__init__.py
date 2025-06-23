"""async_timeout stub."""

from __future__ import annotations

from contextlib import asynccontextmanager


@asynccontextmanager
async def timeout(*args, **kwargs):  # type: ignore[unused-argument]
    yield
