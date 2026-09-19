import uuid

from fastapi import UploadFile, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, exists
from sqlalchemy.orm import selectinload

from app.models.documents import Document,DocumentPermission
from app.models.groups import GroupMember
from app.storage.interface import StorageBackend
from app.schemas.documents import DocumentVisibility
from app.services.ingestion import PDFProcessor
from app.services.permissions import resolve_accessible_document_ids


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
            processor = PDFProcessor(storage_key,self.db,document)
            
            background_tasks.add_task(processor.process_document)

            
            await self.db.commit()
            await self.db.refresh(document)

            return document

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