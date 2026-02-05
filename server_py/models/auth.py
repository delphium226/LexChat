from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )

class UserBase(CamelModel):
    username: str
    pass

class UserCreate(UserBase):
    password: str
    email: str | None = None
    role: str = "user"

class UserResponse(UserBase):
    id: int
    role: str
    dark_mode: bool = False
    
class LoginRequest(CamelModel):
    username: str
    password: str
    remember_me: bool = False

class LoginResponse(CamelModel):
    token: str
    user: UserResponse
