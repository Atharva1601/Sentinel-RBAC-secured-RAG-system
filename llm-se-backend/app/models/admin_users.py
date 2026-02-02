from pydantic import BaseModel
from typing import Optional


class UserCreateRequest(BaseModel):
    username: str
    role_level: int
    clearance_level: int
    department: str


class UserUpdateRequest(BaseModel):
    role_level: Optional[int] = None
    clearance_level: Optional[int] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None
