import uuid

from fastapi import UploadFile, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, exists
from sqlalchemy.orm import selectinload

from app.models.documents import Document,DocumentPermission
from app.models.groups import GroupMember
from app.models.company import CompanyMember
from app.storage.interface import StorageBackend
from app.schemas.documents import DocumentVisibility
from app.services.ingestion import DocumentProcessor
from app.services.permissions import resolve_accessible_document_ids
# from app.models.chat import ChatSession

class DocumentService:

    def __init__(
        self,
        db: AsyncSession,
        storage: StorageBackend,
    ):
        self.db = db
        self.storage = storage

    async def upload_document(
    self,
    company_id,
    uploaded_by,
    file: UploadFile,
    document_name: str,
    document_type: str,
    document_category: str,
    visibility: DocumentVisibility,
    background_tasks: BackgroundTasks,
):
        document = Document(
            company_id=company_id,
            uploaded_by=uploaded_by,
            name=document_name,
            original_filename=file.filename,
            document_type=document_type,
            category=document_category,
            storage_key="",
            mime_type=file.content_type,
            visibility=visibility,
        )

        self.db.add(document)

        # Generate/populate document.id
        await self.db.flush()

        if visibility == DocumentVisibility.RESTRICTED:
            document_permissions = DocumentPermission(
                document_id=document.id,
                group_id=None,
                user_id=uploaded_by,
                company_id=company_id,
            )
            self.db.add(document_permissions)

        storage_key = None

        try:
            storage_key = await self.storage.save(
                company_id=company_id,
                document_id=document.id,
                filename=file.filename,
                file=file,
            )

            document.storage_key = storage_key
            processor = DocumentProcessor(storage_key,self.db,document)
            
            background_tasks.add_task(processor.process_document)

            # new_chat_session=ChatSession(
            #     user_id=uploaded_by,
            #     company_id=company_id,
            #     title=file.filename,
            #     document_ids=[str(document.id)]
            # )
            # self.db.add(new_chat_session)

            await self.db.commit()
            await self.db.refresh(document)
            # await self.db.refresh(new_chat_session)

            return {
                "document": document,
                # "session_id": str(new_chat_session.id),
            }

        except Exception:
            await self.db.rollback()

            if storage_key:
                await self.storage.delete(storage_key)

            raise

    async def list_documents(self, company_id, user_id):
        accessible = await resolve_accessible_document_ids(self.db, company_id, user_id)
        stmt = (
            select(Document)
            .where(Document.company_id == company_id)
            .where(Document.id.in_(accessible))
            .options(selectinload(Document.permissions))
        )

        result = await self.db.execute(stmt)

        return result.scalars().all()

    async def get_document(self, company_id, document_id, user_id):
        accessible = await resolve_accessible_document_ids(self.db,company_id, user_id)
        stmt = (
            select(Document)
            .where(Document.company_id == company_id)
            .where(Document.id == document_id)
            .where(Document.id.in_(accessible))
            .options(selectinload(Document.permissions))
        )

        result = await self.db.execute(stmt)

        return result.scalars().first()

    async def update_visibility(self, company_id, document_id, visibility, updated_by):
        stmt = (
            select(Document)
            .where(Document.company_id == company_id)
            .where(Document.id == document_id)
            .options(selectinload(Document.permissions))
        )
        result = await self.db.execute(stmt)
        document = result.scalars().first()

        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if document.uploaded_by != updated_by:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to update this document.",
            )

        document.visibility = visibility

        if visibility == DocumentVisibility.RESTRICTED:
            stmt = (
                select(DocumentPermission)
                .where(DocumentPermission.document_id == document_id)
                .where(DocumentPermission.user_id == updated_by)
            )
            result = await self.db.execute(stmt)
            if result.scalars().first() is None:
                self.db.add(DocumentPermission(
                    document_id=document_id,
                    group_id=None,
                    user_id=updated_by,
                    company_id=company_id,
                ))

        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def update_user_permissions(self, company_id, document_id, user_ids, updated_by):
        stmt = (
            select(Document)
            .where(Document.company_id == company_id)
            .where(Document.id == document_id)
            .options(selectinload(Document.permissions))
        )
        result = await self.db.execute(stmt)
        document = result.scalars().first()

        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if document.uploaded_by != updated_by:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to update this document.",
            )
        if document.visibility != DocumentVisibility.RESTRICTED:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Document is still 'company_wide'. Restrict it via "
                    "PATCH /api/documents/{id}/permissions first."
                ),
            )

        stmt = (
            select(CompanyMember.user_id)
            .where(
                CompanyMember.company_id == company_id,
                CompanyMember.user_id.in_(user_ids),
                CompanyMember.status == "active",
            )
        )
        result = await self.db.execute(stmt)
        valid_user_ids = set(result.scalars().all())
        invalid_user_ids = set(user_ids) - valid_user_ids
        if invalid_user_ids:
            raise HTTPException(
                status_code=400,
                detail="One or more users are not active members of this company.",
            )

        valid_user_ids.add(updated_by)

        stmt = (
            select(DocumentPermission.user_id)
            .where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.group_id.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        existing_user_ids = set(result.scalars().all())

        if existing_user_ids != valid_user_ids:
            additions = valid_user_ids - existing_user_ids
            deletions = existing_user_ids - valid_user_ids

            for user_id in additions:
                self.db.add(DocumentPermission(
                    document_id=document_id,
                    group_id=None,
                    user_id=user_id,
                    company_id=company_id,
                ))

            if deletions:
                stmt = (
                    select(DocumentPermission)
                    .where(
                        DocumentPermission.document_id == document_id,
                        DocumentPermission.group_id.is_(None),
                        DocumentPermission.user_id.in_(deletions),
                    )
                )
                result = await self.db.execute(stmt)
                for row in result.scalars().all():
                    await self.db.delete(row)

            await self.db.commit()
            await self.db.refresh(document)

        return document

    async def delete_document(self, company_id,document_id):
        stmt = (
            select(Document)
            .where(Document.company_id == company_id)
            .where(Document.id == document_id)
            .options(selectinload(Document.permissions))
        )

        result = await self.db.execute(stmt)
        document = result.scalars().first()
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if document.storage_key:
            await self.storage.delete(document.storage_key)
        await self.db.delete(document)
        await self.db.commit()
        return {"message": "Document deleted successfully"}