import uuid
from fastapi import HTTPException
from app.core.tenant_db import AsyncSession
from app.schemas.chat import ChatQueryResponse,MessageRole,ChatSessionResponse,ChatMessageResponse
from app.services.chat_graph.graph import build_chart_graph
from app.services.chat_graph.state import ChatState
from app.services.chat_graph.debug import run_retrieval_debug
from app.core.rate_limit import check_rate_limit
from app.models.chat import ChatMessage, ChatSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from langchain_core.messages import HumanMessage
from langsmith.run_helpers import tracing_context
import logging

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 2000


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

        if len(question) > MAX_QUESTION_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Question is too long (max {MAX_QUESTION_LENGTH} characters).",
            )

        check_rate_limit(str(user_id))

        # try:
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.company_id == company_id,
                ChatSession.user_id == user_id,
            )
        )

        session_data = result.scalar_one_or_none()

        # except SQLAlchemyError:
        #     logger.exception(
        #         "Failed to fetch chat session. "
        #         "session_id=%s company_id=%s user_id=%s",
        #         session_id,
        #         company_id,
        #         user_id,
        #     )

        #     raise HTTPException(
        #         status_code=500,
        #         detail="Failed to retrieve chat session.",
        #     )

        if session_data is None:
            new_chat_session = ChatSession(
                id=session_id,
                user_id=user_id,
                company_id=company_id,
                title=question.strip(),
            )
            try:
                self.db.add(new_chat_session)
                await self.db.commit()
                await self.db.refresh(new_chat_session)

            except IntegrityError:
                await self.db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="Session id is already in use.",
                )

            except SQLAlchemyError:
                await self.db.rollback()
                logger.exception(
                    "Failed to create chat session. session_id=%s",
                    session_id,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create chat session.",
                )

            session_id = new_chat_session.id
            session_data = new_chat_session

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
            # Named + tagged with tenant/session metadata so this request's trace is
            # findable in the LangSmith project by session_id/company_id/user_id,
            # rather than one of many identically-named, anonymous "LangGraph" runs —
            # see build_docs/08-observability-and-guardrails.md §1.3.
            with tracing_context(
                metadata={
                    "company_id": str(company_id),
                    "user_id": str(user_id),
                    "session_id": str(session_id),
                },
                tags=["chat.query"],
            ):
                final_state = await graph.ainvoke(
                    ChatState(
                        question=question.strip(),
                        company_id=company_id,
                        user_id=user_id,
                        messages=[
                            HumanMessage(content=question)
                        ],
                        session_id=session_id,
                        conversation_history= [],
                        retrieved_chunks= [],
                        accessible_document_ids= [],
                        tool_call_count=0,
                        usage={},
                    ),
                    config={"run_name": "chat.query"},
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
        usage = final_state.get("usage") or {}

        logger.info(
            "Chat query token usage: session_id=%s input=%s output=%s total=%s",
            session_id,
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            usage.get("total_tokens"),
        )

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
            usage=usage,
        )


    async def retrieval_debug(
        self,
        question: str,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
    ) -> dict:
        if role not in ("owner", "admin"):
            raise HTTPException(
                status_code=403,
                detail="Retrieval debug is restricted to owner/admin accounts.",
            )

        if not question or not question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty.")

        try:
            return await run_retrieval_debug(
                self.db, company_id, user_id, question.strip()
            )
        except Exception:
            logger.exception(
                "Retrieval debug failed. company_id=%s user_id=%s",
                company_id,
                user_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to run retrieval debug.",
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
        except SQLAlchemyError:
            logger.exception(
                "Failed to list chat sessions. company_id=%s user_id=%s",
                company_id,
                user_id,
            )
            raise HTTPException(status_code=500, detail="Failed to list chat sessions.")


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
        except SQLAlchemyError:
            logger.exception(
                "Failed to list chat messages. session_id=%s company_id=%s user_id=%s",
                session_id,
                company_id,
                user_id,
            )
            raise HTTPException(status_code=500, detail="Failed to list chat messages.")


    async def delete_session(self, session_id: str, company_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        stmt = (
            select(ChatSession)
            .where(ChatSession.id == session_id)
            .where(ChatSession.company_id == company_id)
            .where(ChatSession.user_id == user_id)
        )

        try:
            result = await self.db.execute(stmt)
        except SQLAlchemyError:
            logger.exception(
                "Failed to fetch chat session for deletion. session_id=%s",
                session_id,
            )
            raise HTTPException(status_code=500, detail="Failed to delete session.")

        session = result.scalars().first()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        try:
            await self.db.delete(session)
            await self.db.commit()
        except SQLAlchemyError:
            await self.db.rollback()
            logger.exception(
                "Failed to delete chat session. session_id=%s",
                session_id,
            )
            raise HTTPException(status_code=500, detail="Failed to delete session.")

        return {"message": "Session deleted successfully"}
