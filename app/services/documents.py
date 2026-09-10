from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Document,DocumentPermission
from app.storage.interface import StorageBackend
from app.schemas.documents import DocumentVisibility

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

            await self.db.commit()
            await self.db.refresh(document)

            return document

        except Exception:
            await self.db.rollback()

            if storage_key:
                await self.storage.delete(storage_key)

            raise
