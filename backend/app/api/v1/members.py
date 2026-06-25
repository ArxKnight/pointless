from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DepartmentMember, Team, User
from app.schemas.api import MemberCreate, MemberOut, MemberUpdate
from app.services.auth_service import hash_password, require_admin

router=APIRouter(prefix="/members", tags=["members"])
@router.get("", response_model=list[MemberOut])
def list_members(db:Session=Depends(get_db), admin:User=Depends(require_admin)):
    return db.query(DepartmentMember).order_by(DepartmentMember.display_name).all()
@router.post("", response_model=MemberOut)
def create_member(data:MemberCreate, db:Session=Depends(get_db), admin:User=Depends(require_admin)):
    if db.query(DepartmentMember).filter(DepartmentMember.email==data.email).first(): raise HTTPException(409,"Member email exists")
    if data.team_id is not None:
        team = db.get(Team, data.team_id)
        if not team or not team.is_active: raise HTTPException(404,"Active team not found")
    m=DepartmentMember(display_name=data.display_name,email=data.email,added_by=admin.id,active=True); db.add(m)
    if data.username and data.password:
        if db.query(User).filter(User.username==data.username).first(): raise HTTPException(409,"Username exists")
        db.add(User(username=data.username,display_name=data.display_name,email=data.email,password_hash=hash_password(data.password),is_admin=data.is_admin,is_active=True,team_id=data.team_id))
    db.commit(); db.refresh(m); return m
@router.patch("/{member_id}", response_model=MemberOut)
def update_member(member_id:int,data:MemberUpdate,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    m=db.get(DepartmentMember,member_id)
    if not m: raise HTTPException(404,"Member not found")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(m,k,v)
    db.commit(); db.refresh(m); return m
