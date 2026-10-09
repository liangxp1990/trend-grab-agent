"""SQLAlchemy 数据库会话管理。

平台库（platform.db）仅由 webapp 单一进程写入，开启 WAL 以支持
API 读写与 WebSocket 并发。日库（output/**/*.db）由引擎独占写，
webapp 只读访问（见 routers/data_api.py），二者物理分离。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import SETTINGS


class Base(DeclarativeBase):
    """ORM 声明基类。"""


_engine = create_engine(
    f"sqlite:///{SETTINGS.db_path}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(_engine, "connect")
def _set_sqlite_wal(dbapi_connection, _connection_record) -> None:
    """为每个新连接开启 WAL 与外键约束（SQLite 并发读写前提）。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)


def init_db() -> None:
    """按 ORM 模型建表（幂等）。

    说明：当前为全新库直接 create_all；引入字段演进需求时再接 Alembic，
    模型已按迁移友好方式组织（显式主键/索引）。
    """
    from . import models  # noqa: F401 确保模型注册

    Base.metadata.create_all(bind=_engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """提供事务范围的会话上下文，异常自动回滚。

    Yields:
        SQLAlchemy 会话。
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
