from app.core.tenant_db import AsyncSession

class ChatService:
    def __init__(self,db:AsyncSession):
        self.db = db

    async def query(self, query: str) -> str:
        return "works!!"

