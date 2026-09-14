from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Sentinel "schema" used on every tenant-scoped model's __table_args__ (see
# app/models/documents.py, app/models/groups.py). It is never a real Postgres
# schema — at connection time it gets swapped for the caller's actual
# "tenant_<company_id>" schema via `execution_options(schema_translate_map=...)`.
# See app/core/tenant_db.py for where that swap happens per-request, and
# build_docs/06-schema-per-tenant-migration.md for the full design writeup.
TENANT_SCHEMA = "tenant"


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
