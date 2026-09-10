from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.dependencies import get_db
from fastapi import Depends
from app.routers import company , auth, employee, documents

app = FastAPI()

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(company.router, prefix="/api/company", tags=["Company"])
app.include_router(employee.router, prefix="/api/employees", tags=["Employees"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])

@app.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected",
        "database_result": result.scalar(),
    }


# uv run uvicorn app.main:app --reload