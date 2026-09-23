import uuid

from app.core.tenant_db import AsyncSession
from app.schemas.chat import ChatQueryResponse,MessageRole,ChatSessionResponse,ChatMessageResponse
from app.services.chat_graph.graph import build_chart_graph
from app.services.chat_graph.state import ChatState
from app.models.chat import ChatMessage, ChatSession
from sqlalchemy import select


class ChatService:
    def __init__(self,db:AsyncSession):
        self.db = db
        
    async def query(self, question: str, company_id: uuid.UUID, user_id: uuid.UUID,session_id:str) -> ChatQueryResponse:
        
        graph = build_chart_graph(self.db)

        new_chat_message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            company_id=company_id,
            role=MessageRole.USER,
            content=question,
        )
        self.db.add(new_chat_message)
        await self.db.commit()
        final_state = await graph.ainvoke(ChatState(
            question=question,
            company_id=company_id,
            user_id=user_id,
        ))
        
        new_assistant_message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            company_id=company_id,
            role=MessageRole.ASSISTANT,
            content=final_state["answer"],
            sources=final_state["sources"],
        )
        self.db.add(new_assistant_message)
        await self.db.commit()
        
        return ChatQueryResponse(
            answer=final_state["answer"],
            sources=final_state["sources"],
        )

    async def list_sessions(self, company_id: uuid.UUID, user_id: uuid.UUID) -> list[ChatSessionResponse]:
        stmt = (
            select(ChatSession)
            .where(ChatSession.company_id == company_id)
            .where(ChatSession.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_messages(self, session_id: str, company_id: uuid.UUID, user_id: uuid.UUID) -> list[ChatMessageResponse]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.company_id == company_id)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()


    async def delete_session(self, session_id: str, company_id: uuid.UUID, user_id: uuid.UUID) -> ChatSessionResponse:
        return []

