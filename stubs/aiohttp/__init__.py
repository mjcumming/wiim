"""Minimal aiohttp stub for unit tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any


class ClientError(Exception):
    pass


class ClientSession:  # minimal
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.closed = False

    async def request(self, *args: Any, **kwargs: Any) -> None:
        raise ClientError("aiohttp stub – network calls disabled in tests")

    async def close(self) -> None:
        self.closed = True


class ClientTimeout:  # pylint: disable=too-few-public-methods
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass


@asynccontextmanager
async def timeout(*args: Any, **kwargs: Any) -> AsyncGenerator[None, None]:
    yield
