"""Minimal aiohttp stub for unit tests."""

from __future__ import annotations

from contextlib import asynccontextmanager


class ClientError(Exception):
    pass


class ClientSession:  # minimal
    def __init__(self, *args, **kwargs):
        self.closed = False

    async def request(self, *args, **kwargs):
        raise ClientError("aiohttp stub – network calls disabled in tests")

    async def close(self):
        self.closed = True


class ClientTimeout:  # pylint: disable=too-few-public-methods
    def __init__(self, *args, **kwargs):
        pass


@asynccontextmanager
async def timeout(*args, **kwargs):
    yield
