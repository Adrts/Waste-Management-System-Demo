"""演示级单角色登录（内存 token）。"""
import secrets

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

TOKENS: dict[str, dict] = {}

USER = {"username": "admin", "password": "haikou123", "name": "演示管理员", "role": "admin"}


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody):
    if body.username != USER["username"] or body.password != USER["password"]:
        return {"code": 1, "message": "用户名或密码错误"}
    token = secrets.token_hex(16)
    info = {"name": USER["name"], "role": USER["role"], "username": USER["username"]}
    TOKENS[token] = info
    return {"code": 0, "data": {"token": token, "user": info}}
