from fastapi import APIRouter
from app.services.chat import ChatService
from app.core.security import CurrentUser
from app.core.tenant_db import get_tenant_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

router = APIRouter()


def get_chat_service(db: AsyncSession = Depends(get_tenant_db)) -> ChatService:
    return ChatService(db)


@router.post("/query")
async def query_endpoint(
    query: str, 
    current_user: CurrentUser, 
    service: ChatService = Depends(get_chat_service)
):
    return {"data": await service.query(query)}