from fastapi import APIRouter, status
from app.services.chat import ChatService
from app.core.security import CurrentUser
from app.core.tenant_db import get_tenant_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse, ChatSessionResponse , ChatMessageResponse

router = APIRouter()


def get_chat_service(db: AsyncSession = Depends(get_tenant_db)) -> ChatService:
    return ChatService(db)



@router.post("/query", response_model=ChatQueryResponse)
async def query_endpoint(
    session_id: str,
    request: ChatQueryRequest,
    current_user: CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    return await service.query(
        session_id=session_id,
        question=request.query,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )

@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    current_user: CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    return await service.list_sessions(
        company_id=current_user.company_id,
        user_id=current_user.id,
    )

@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def list_messages(
    session_id: str,
    current_user: CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    return await service.list_messages(
        session_id=session_id,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )

@router.delete("/sessions/{session_id}",status_code=status.HTTP_200_OK)
async def delete_session(
    session_id: str,
    current_user: CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    return await service.delete_session(
        session_id=session_id,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )