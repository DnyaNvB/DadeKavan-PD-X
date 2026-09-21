from __future__ import annotations

from functools import lru_cache

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from common.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache

def get_engine() -> AsyncEngine:
    settings = get_settings()
    url = URL.create(
        drivername="mysql+asyncmy",
        username=settings.mysql_user,
        password=settings.mysql_password,
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
        query={"charset": "utf8mb4"},
    )
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=10,
        max_overflow=20,
    )


@lru_cache

def get_session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
