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
    model_config = ConfigDict(from_attributes=True)