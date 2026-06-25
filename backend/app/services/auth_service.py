from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
ALGORITHM = "HS256"

def hash_password(password: str) -> str: return pwd_context.hash(password)
def verify_password(password: str, hashed: str) -> bool: return pwd_context.verify(password, hashed)

def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user.id), "username": user.username, "admin": user.is_admin, "exp": expire}, settings.secret_key, algorithm=ALGORITHM)

def authenticate(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user and verify_password(password, user.password_hash): return user
    return None

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "): token = auth.split(" ", 1)[1]
    if not token: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, user_id)
    if not user or not user.is_active: raise HTTPException(status_code=401, detail="Inactive user")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin: raise HTTPException(status_code=403, detail="Admin only")
    return user
