from pydantic import BaseModel, EmailStr

class RegisterReq(BaseModel):
    client_id: str   # "C001"
    email: EmailStr
    password: str

class LoginReq(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"