from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid

class CompanySignupSchema(BaseModel):
    email:str
    password:str
    owner_name:str
    company_name:str
    plan:str

class CompanyLoginSchema(BaseModel):
    email:str
    password:str

class RefreshTokenSchema(BaseModel):
    refresh_token: str

class CompanyCreateSchema(BaseModel):
    name:str
    plan:str

class CompanyUpdateSchema(BaseModel):
    name:str
    plan:str
    is_active:bool
    model_config = ConfigDict(from_attributes=True)

class CompanyResponseSchema(BaseModel):
    id: uuid.UUID
    name:str
    plan:str
    slug:str
    is_active:bool
    created_at:datetime
    model_config = ConfigDict(from_attributes=True)
    