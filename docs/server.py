import logging
from datetime import datetime, timedelta, timezone

import jwt
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# ============== 日志 ==============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auth")

# ============== FastAPI 实例 ==============
app = FastAPI(title="仿真接口测试服务", version="2.0")

# ============== 安全方案（Swagger 自动出 Authorize 按钮） ==============
security = HTTPBearer()

# ============== 常量 ==============
SECRET_KEY = "test_api_secret_key_2026_abc123xyz"
ALGORITHM = "HS256"
VALID_USER = {"username": "admin", "password": "123456"}

user_data = {"id": 1, "name": "测试用户", "age": 20}


# ============== 入参模型 ==============
class LoginReq(BaseModel):
    username: str
    password: str


class CreateUser(BaseModel):
    name: str
    age: int


class UpdateUser(BaseModel):
    name: str


# ============== Token 生成 ==============
def create_jwt_token(user_id: int) -> str:
    """sub 必须为字符串：PyJWT 2.x 强制校验 InvalidSubjectError"""
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload = {"sub": str(user_id), "exp": expire}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


# ============== 认证依赖（所有 CRUD 接口共享） ==============
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    FastAPI 标准 Bearer Token 依赖。
    Swagger UI 中点击右上角 🔓 Authorize，粘贴纯 token（不带 Bearer 前缀）
    即可全站生效，无需每个接口手动填 Header。
    """
    token = credentials.credentials
    logger.info(f"收到 Token 前20字符: {token[:20]}...")

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_signature": True, "verify_exp": True},
        )
        logger.info(f"Token 校验通过: sub={payload.get('sub')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token 已过期")
        raise HTTPException(status_code=401, detail="Token已过期")
    except jwt.InvalidSignatureError:
        logger.warning("Token 签名无效")
        raise HTTPException(status_code=401, detail="Token签名无效")
    except jwt.DecodeError as e:
        logger.warning(f"Token 解码失败: {e}")
        raise HTTPException(status_code=401, detail="Token格式错误")
    except jwt.InvalidTokenError as e:
        logger.warning(f"无效 Token: {e}")
        raise HTTPException(status_code=401, detail="非法无效Token")


# ============== 登录接口（无需认证） ==============
@app.post("/api/login", summary="登录获取JWT Token")
def login(req: LoginReq):
    if req.username == VALID_USER["username"] and req.password == VALID_USER["password"]:
        token = create_jwt_token(user_id=1)
        logger.info(f"用户 {req.username} 登录成功，签发 Token")
        return {
            "code": 200,
            "msg": "登录成功",
            "data": {"access_token": token, "token_type": "Bearer"},
        }
    raise HTTPException(status_code=400, detail="账号或密码错误")


# ============== CRUD 接口（需认证） ==============
@app.get("/api/user", summary="GET查询用户")
def get_user(user_id: int = 1, user: dict = Depends(get_current_user)):
    return {"code": 200, "msg": "GET成功", "data": user_data}


@app.post("/api/user", summary="POST新增用户")
def add_user(info: CreateUser, user: dict = Depends(get_current_user)):
    global user_data
    user_data = {"id": 2, "name": info.name, "age": info.age}
    return {"code": 200, "msg": "POST创建成功", "data": user_data}


@app.put("/api/user", summary="PUT更新用户")
def edit_user(info: UpdateUser, user: dict = Depends(get_current_user)):
    global user_data
    user_data["name"] = info.name
    return {"code": 200, "msg": "PUT更新成功", "data": user_data}


@app.delete("/api/user", summary="DELETE删除用户")
def del_user(user_id: int = 1, user: dict = Depends(get_current_user)):
    global user_data
    user_data = {}
    return {"code": 200, "msg": "DELETE删除成功", "data": user_data}


# ============== 启动入口 ==============
if __name__ == "__main__":
    logger.info("启动仿真接口测试服务 http://127.0.0.1:8011")
    uvicorn.run(app, host="127.0.0.1", port=8011)
