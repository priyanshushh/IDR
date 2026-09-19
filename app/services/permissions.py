import uuid

from sqlalchemy import select, or_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Document, DocumentPermission
from app.models.groups import GroupMember
from app.schemas.documents import DocumentVisibility


async def resolve_accessible_document_ids(
    db: AsyncSession,
    company_id,
    user_id,
) -> list[uuid.UUID]:
    """Every document ID `user_id` is allowed to see: company-wide documents, plus
    any RESTRICTED document explicitly shared with them directly or via a group
    they belong to. Shared between DocumentService and ChatService — the exact same
    check has to gate both "can list/view this document" and "can this chat answer
    cite this document's chunks.\""""
    user_group_ids = select(GroupMember.group_id).where(GroupMember.user_id == user_id)

    stmt = select(Document.id).where(
        Document.company_id == company_id,
        or_(
            Document.visibility == DocumentVisibility.COMPANY_WIDE,
            exists().where(
                DocumentPermission.document_id == Document.id,
                or_(
                    DocumentPermission.user_id == user_id,
                    DocumentPermission.group_id.in_(user_group_ids),
                ),
            ),
        ),
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())