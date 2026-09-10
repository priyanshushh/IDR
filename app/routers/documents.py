# Storage: write uploaded files to a local folder (e.g. ./storage/{company_id}/{document_id}/filename) behind a small 
#StorageBackend interface with one method each for save/read/delete. Keeping that interface
# thin now is what makes swapping in S3 at Stage 11 a config change instead of a rewrite.
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
