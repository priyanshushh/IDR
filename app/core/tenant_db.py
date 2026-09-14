from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app.core.security import CurrentUser
from app.database.database import AsyncSessionLocal, TENANT_SCHEMA


async def get_tenant_db(currentuser: CurrentUser) -> AsyncGenerator[AsyncSession, None]:
    """DB session scoped to the caller's tenant schema.

    Every tenant-scoped model (Document, DocumentPermission, Group, GroupMember)
    is declared with the TENANT_SCHEMA sentinel in its __table_args__. Setting
    schema_translate_map on this session's connection is what turns that sentinel
    into the caller's real "tenant_<company_id>" schema for every query issued
    through this session — no per-query WHERE clause required for the isolation
    itself (company_id filters in the service layer remain as defense-in-depth).

    Use this instead of `get_db` in any router/service that touches a
    tenant-scoped table. Routes that only touch global tables (users, company,
    company_members, refresh_tokens) should keep using `get_db`.

    Why an `after_begin` event instead of one `session.connection(execution_
    options=...)` call: `execution_options` set that way only lasts for the
    *current* transaction. Several service methods `commit()` mid-method and
    then keep using the same session (e.g. `GroupService.create_group` does
    `commit()` then `refresh()`) — `commit()` ends that transaction, and the
    next statement silently starts a fresh one with no schema mapping at all,
    which resolves the TENANT_SCHEMA sentinel to a literal (nonexistent)
    "tenant" schema instead of the real one. Found by actually running this
    end to end against a live database; see
    build_docs/06-schema-per-tenant-migration.md §7. Listening for
    `after_begin` re-applies the mapping on *every* transaction this session
    opens, including ones that start implicitly after a commit.
    """
    async with AsyncSessionLocal() as session:
        schema_translate_map = {TENANT_SCHEMA: currentuser.schema_name}

        @event.listens_for(session.sync_session, "after_begin")
        def _apply_schema_translate_map(
            sync_session: SyncSession, transaction, connection: Connection
        ) -> None:
            connection.execution_options(schema_translate_map=schema_translate_map)

        yield session


TenantDB = Annotated[AsyncSession, Depends(get_tenant_db)]
