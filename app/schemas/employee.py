from pydantic import BaseModel
from typing import Optional,Literal

class InviteEmployeeSchema(BaseModel):
    name: str
    email: str
    role: str
    must_change_password: Optional[bool] = True

class UpdatedEmployee(BaseModel):
    update_key: Literal["name", "email", "role", "must_change_password","status"]
    update_key_value: str|bool

class UpdatePassword(BaseModel):
    old_password:str
    new_password:str    