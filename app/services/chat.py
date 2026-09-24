import uuid
from fastapi import HTTPException
from app.core.tenant_db import AsyncSession
from app.schemas.chat import ChatQueryResponse,MessageRole,ChatSessionResponse,ChatMessageResponse
from app.services.chat_graph.graph import build_chart_graph
from app.services.chat_graph.state import ChatState
from app.models.chat import ChatMessage, ChatSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

import logging 

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self,db:AsyncSession):
        self.db = db
        
    async def query(
        self,
        question: str,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> ChatQueryResponse:
        if not question or not question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty.",
            )

        try:
            result = await self.db.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.company_id == company_id,
                    ChatSession.user_id == user_id,
                )
            )

            session_data = result.scalar_one_or_none()

        except SQLAlchemyError:
            logger.exception(
                "Failed to fetch chat session. "
                "session_id=%s company_id=%s user_id=%s",
                session_id,
                company_id,
                user_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve chat session.",
            )

        if session_data is None:
            raise HTTPException(
                status_code=404,
                detail="Chat session not found.",
            )

        try:
            graph = build_chart_graph(self.db)

        except Exception:
            logger.exception(
                "Failed to build chat graph. session_id=%s",
                session_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Failed to initialize chat processing.",
            )

        new_chat_message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            company_id=company_id,
            role=MessageRole.USER,
            content=question.strip(),
        )

        try:
            self.db.add(new_chat_message)
            await self.db.commit()

        except SQLAlchemyError:
            await self.db.rollback()

            logger.exception(
                "Failed to save user chat message. session_id=%s",
                session_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Failed to save your message.",
            )

        try:
            final_state = await graph.ainvoke(
                ChatState(
                    question=question.strip(),
                    company_id=company_id,
                    user_id=user_id,
                )
            )

        except Exception:
            logger.exception(
                "Chat graph execution failed. session_id=%s",
                session_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Failed to process your question.",
            )

        answer = final_state.get("answer")
        sources = final_state.get("sources", [])

        if not answer:
            logger.error(
                "Chat graph returned no answer. session_id=%s",
                session_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Chat processing returned an invalid response.",
            )

        new_assistant_message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            company_id=company_id,
            role=MessageRole.ASSISTANT,
            content=answer,
            sources=sources,
        )

        try:
            self.db.add(new_assistant_message)
            session_data.title = question.strip()

            await self.db.commit()

        except SQLAlchemyError:
            await self.db.rollback()

            logger.exception(
                "Failed to save assistant response. session_id=%s",
                session_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Failed to save the chat response.",
            )

        return ChatQueryResponse(
            answer=answer,
            sources=sources,
        )


    async def list_sessions(self, company_id: uuid.UUID, user_id: uuid.UUID) -> list[ChatSessionResponse]:
        try:
            stmt = (
                select(ChatSession)
                .where(ChatSession.company_id == company_id)
                .where(ChatSession.user_id == user_id)
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))


    async def list_messages(self, session_id: str, company_id: uuid.UUID, user_id: uuid.UUID) -> list[ChatMessageResponse]:
        try:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .where(ChatMessage.company_id == company_id)
                .where(ChatMessage.user_id == user_id)
                .order_by(ChatMessage.created_at.asc())
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))


    async def delete_session(self, session_id: str, company_id: uuid.UUID, user_id: uuid.UUID) -> ChatSessionResponse:
        try:
            stmt = (
                select(ChatSession)
                .where(ChatSession.id == session_id)
                .where(ChatSession.company_id == company_id)
                .where(ChatSession.user_id == user_id)
            )
            result = await self.db.execute(stmt)
            session = result.scalars().first()
            if session:
                await self.db.delete(session)
                await self.db.commit()
            return {"message":"Session deleted successfully"}
        except:
            raise HTTPException(status_code=404, detail="Session not found")
