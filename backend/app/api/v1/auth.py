from collections import defaultdict, deque
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas.api import LoginIn, UserOut
from app.services.auth_service import authenticate, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
_attempts = defaultdict(deque)

@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    now = datetime.utcnow(); bucket = _attempts[ip]
    while bucket and bucket[0] < now - timedelta(minutes=1): bucket.popleft()
    if len(bucket) >= 5: raise HTTPException(status_code=429, detail="Too many login attempts")
    user = authenticate(db, data.username, data.password)
    if not user:
        bucket.append(now); raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user)
    user.last_login_at = datetime.utcnow()
    db.commit()
    response.set_cookie("access_token", token, httponly=True, samesite="lax", secure=settings.cookie_secure, max_age=settings.access_token_expire_minutes*60)
    return {"user": UserOut.model_validate(user)}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}

@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)): return user
