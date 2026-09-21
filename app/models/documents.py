from sqlalchemy import String, Boolean, DateTime, ForeignKey, BigInteger, Any
from sqlalchemy.orm import Mapped, mapped_column,relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database.database import Base, TENANT_SCHEMA
from sqlalchemy import Text
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime
from sqlalchemy import func
from typing import Any


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"schema": TENANT_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # No FK to company.id — this table lives in a per-tenant schema, so the
    # schema itself is the tenant boundary; company_id is kept only as a
    # denormalized defense-in-depth column (build_docs/02-architecture.md §2.5).
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # No FK to users.id — users is global/public, this table is per-tenant;
    # see the company_id note above for the cross-schema-FK trade-off.
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    source:Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="upload",
    )

    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    visibility: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="company_wide",
    )

    # Tracks the async extract -> chunk -> embed pipeline (build_docs
    # 08-pgvector-migration-guide.md Part 5): pending right after upload,
    # processing while the background job runs, then ready/failed.
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    permissions = relationship(
        "DocumentPermission",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DocumentPermission(Base):
    __tablename__ = "document_permissions"
    __table_args__ = {"schema": TENANT_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # documents.id and groups.id are in the same tenant schema, so these two
    # FKs stay real constraints — schema_translate_map resolves both sides
    # consistently at execution time.
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{TENANT_SCHEMA}.documents.id"),
        nullable=False,
        index=True,
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{TENANT_SCHEMA}.groups.id"),
        nullable=True,
        index=True,
    )
    # No FK to users.id/company.id — both are global/public tables; see the
    # cross-schema-FK note on Document.company_id above.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    document = relationship(
        "Document",
        back_populates="permissions",
    )




class DocumentChunks(Base):
    __tablename__ = "document_chunks"
    __table_args__ = {"schema": TENANT_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{TENANT_SCHEMA}.documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    embedding: Mapped[Vector] = mapped_column(
        Vector(384),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )

    # Python attribute avoids the name `metadata` — that's reserved on SQLAlchemy's
    # declarative Base (Base.metadata is the MetaData registry) — but the actual
    # Postgres column is still named "metadata", matching the migration.
    meta_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )