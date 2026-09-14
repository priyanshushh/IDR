from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid

class UserProfileSchema(BaseModel):
    id:uuid.UUID
    name:str
    must_change_password:bool
    email:str
    is_active:bool
    created_at:datetime
    last_login_at:datetime | None
    company_id:uuid.UUID
    role:str
    status:str
    # Internal routing detail (which Postgres schema this company's tenant
    # tables live in) — carried on the request-scoped user profile so
    # app/core/tenant_db.py can set schema_translate_map without an extra DB
    # query. GET /api/auth/me excludes it from the response body (see
    # app/routers/auth.py) since it's an infra detail, not user-facing data.
    schema_name:str
    model_config = ConfigDict(from_attributes=True)