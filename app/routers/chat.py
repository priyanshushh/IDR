from fastapi import APIRouter
from app.services.chat import ChatService
from app.core.security import CurrentUser
from app.core.tenant_db import get_tenant_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse

router = APIRouter()


def get_chat_service(db: AsyncSession = Depends(get_tenant_db)) -> ChatService:
    return ChatService(db)



@router.post("/query", response_model=ChatQueryResponse)
async def query_endpoint(
    request: ChatQueryRequest,
    current_user: CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    return await service.query(
        question=request.query,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )