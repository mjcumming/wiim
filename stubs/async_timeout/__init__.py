"""async_timeout stub."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any


@asynccontextmanager
async def timeout(*args: Any, **kwargs: Any) -> AsyncGenerator[None, None]:
    yield
