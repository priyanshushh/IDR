from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
)

from app.core.security import CurrentUser
from app.core.storage import get_storage
from app.services.documents import DocumentService
from app.storage.interface import StorageBackend
from app.database.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.documents import DocumentVisibility

router = APIRouter()


def get_document_service(
    storage: StorageBackend = Depends(get_storage),
    db: AsyncSession=Depends(get_db)
) -> DocumentService:
    return DocumentService(db,storage)


@router.post("/upload")
async def upload_document(
    currentuser: CurrentUser,
    file: UploadFile = File(...),
    document_name: str = Form(...),
    document_type: str = Form(...),
    document_category: str = Form(...),
    visibility: DocumentVisibility = DocumentVisibility.COMPANY_WIDE,
    service: DocumentService = Depends(get_document_service),
):
    return await service.upload_document(
        company_id=currentuser.company_id,
        uploaded_by=currentuser.id,
        file=file,
        document_name=document_name,
        document_type=document_type,
        document_category=document_category,
        visibility=visibility,
    )

@router.get("/")
async def list_documents(
    currentuser: CurrentUser,
    service: DocumentService = Depends(get_document_service),
):
    return await service.list_documents(company_id=currentuser.company_id)


@router.get("/{id}")
async def get_document(
    id: str,
    currentuser: CurrentUser,
    service: DocumentService = Depends(get_document_service),
):
    return await service.get_document(company_id=currentuser.company_id, document_id=id)


@router.delete("/{id}")
async def delete_document(
    id: str,
    currentuser: CurrentUser,
    service: DocumentService = Depends(get_document_service),
):
    return await service.delete_document(company_id=currentuser.company_id, document_id=id)