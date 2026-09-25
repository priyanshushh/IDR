from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
)
from fastapi import BackgroundTasks
from app.core.security import CurrentUser
from app.core.storage import get_storage
from app.core.tenant_db import get_tenant_db
from app.services.documents import DocumentService
from app.storage.interface import StorageBackend
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.documents import (
    DocumentVisibility,
    DocumentUploadResponse,
    DocumentSchema,
    DocumentVisibilityUpdateRequest,
    DocumentUserPermissionsRequest,
)

router = APIRouter()


def get_document_service(
    storage: StorageBackend = Depends(get_storage),
    db: AsyncSession=Depends(get_tenant_db)
) -> DocumentService:
    return DocumentService(db,storage)


@router.post("/upload",response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
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
        background_tasks=background_tasks
    )

@router.get("/")
async def list_documents(
    currentuser: CurrentUser,
    service: DocumentService = Depends(get_document_service),
):
    return await service.list_documents(company_id=currentuser.company_id,user_id=currentuser.id)


@router.get("/{id}")
async def get_document(
    id: str,
    currentuser: CurrentUser,
    service: DocumentService = Depends(get_document_service),
):
    return await service.get_document(
        company_id=currentuser.company_id, document_id=id, user_id=currentuser.id
    )


@router.patch("/{document_id}/permissions", response_model=DocumentSchema)
async def update_document_visibility(
    document_id: str,
    request: DocumentVisibilityUpdateRequest,
    currentuser: CurrentUser,
    service: DocumentService = Depends(get_document_service),
):
    return await service.update_visibility(
        company_id=currentuser.company_id,
        document_id=document_id,
        visibility=request.visibility,
        updated_by=currentuser.id,
    )


@router.patch("/{document_id}/user-permissions", response_model=DocumentSchema)
async def update_document_user_permissions(
    document_id: str,
    request: DocumentUserPermissionsRequest,
    currentuser: CurrentUser,
    service: DocumentService = Depends(get_document_service),
):
    return await service.update_user_permissions(
        company_id=currentuser.company_id,
        document_id=document_id,
        user_ids=request.user_ids,
        updated_by=currentuser.id,
    )


@router.delete("/{id}")
async def delete_document(
    id: str,
    currentuser: CurrentUser,
    service: DocumentService = Depends(get_document_service),
):
    return await service.delete_document(company_id=currentuser.company_id, document_id=id)