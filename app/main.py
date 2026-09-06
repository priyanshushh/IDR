from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import AsyncSessionLocal

from fastapi import Depends


app = FastAPI()


@app.get("/health")
async def health(
    db: AsyncSession = Depends(AsyncSessionLocal),
):
    result = await db.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected",
        "database_result": result.scalar(),
    }


# uv run uvicorn app.main:app --reload