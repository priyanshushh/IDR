import uuid

from app.core.tenant_db import AsyncSession
from app.schemas.chat import ChatQueryResponse
from app.services.chat_graph.graph import build_chart_graph
from app.services.chat_graph.state import ChatState

class ChatService:
    def __init__(self,db:AsyncSession):
        self.db = db

    async def query(self, question: str, company_id: uuid.UUID, user_id: uuid.UUID) -> ChatQueryResponse:
        
        graph = build_chart_graph(self.db)

        
        final_state = await graph.ainvoke(ChatState(
            question=question,
            company_id=company_id,
            user_id=user_id,
        ))
        
        return ChatQueryResponse(
            answer=final_state["answer"],
            sources=final_state["sources"],
        )

