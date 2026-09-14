from sqlalchemy import String,Boolean,Integer,ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database.database import Base, TENANT_SCHEMA
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime
from sqlalchemy import func

class Group(Base):
    __tablename__ = "groups"
    __table_args__ = {"schema": TENANT_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        unique=True,
        default=uuid.uuid4,
        index=True
    )
    # No FK to company.id: this table lives in a per-tenant schema, so the
    # schema itself *is* the tenant boundary — company_id is kept only as a
    # denormalized defense-in-depth column (see build_docs/02-architecture.md
    # §2.5), and a cross-schema FK constraint would add migration complexity
    # for no isolation benefit.
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # No FK to users.id for the same cross-schema reason as company_id above.
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    updated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
        onupdate=func.now()
    )

class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = {"schema": TENANT_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        unique=True,
        default=uuid.uuid4,
        index=True
    )
    # groups.id is in the same tenant schema, so this FK stays a real
    # constraint — schema_translate_map resolves both sides consistently.
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{TENANT_SCHEMA}.groups.id"))
    # users.id is global/public — no cross-schema FK, see Group.created_by above.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))