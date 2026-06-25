from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DepartmentMember, GivingPlan, PointsLedger, Quarter, User
from app.schemas.api import PlanOut
from app.services.auth_service import get_current_user, require_admin

router=APIRouter(prefix="/plans", tags=["plans"])
def user_member(db,user): return db.query(DepartmentMember).filter(DepartmentMember.email==user.email).first()
def out(p): return {"id":p.id,"quarter_id":p.quarter_id,"from_member_id":p.from_member_id,"to_member_id":p.to_member_id,"from_name":p.from_member.display_name,"to_name":p.to_member.display_name,"amount":p.amount,"acknowledged":p.acknowledged}
@router.get("/me")
def my_plan(db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    q=db.query(Quarter).filter(Quarter.is_active==True,Quarter.is_completed==False).order_by(Quarter.id.desc()).first(); m=user_member(db,user)
    if not q or not m: return {"quarter":None,"outgoing":[],"incoming":[]}
    outgoing=[out(p) for p in db.query(GivingPlan).filter(GivingPlan.quarter_id==q.id, GivingPlan.from_member_id==m.id).all()]
    incoming=[out(p) for p in db.query(GivingPlan).filter(GivingPlan.quarter_id==q.id, GivingPlan.to_member_id==m.id).all()]
    return {"quarter":{"id":q.id,"label":q.label},"member":{"id":m.id,"display_name":m.display_name},"outgoing":outgoing,"incoming":incoming}
@router.get("/me/history")
def my_history(db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    m=user_member(db,user)
    if not m: return []
    data=[]
    for q in db.query(Quarter).order_by(Quarter.year.desc(),Quarter.quarter.desc()).all():
        rows=db.query(GivingPlan).filter(GivingPlan.quarter_id==q.id).filter((GivingPlan.from_member_id==m.id)|(GivingPlan.to_member_id==m.id)).all()
        data.append({"quarter":{"id":q.id,"label":q.label},"plans":[out(p) for p in rows]})
    return data
@router.get("/{quarter_id}")
def all_plan(quarter_id:int, db:Session=Depends(get_db), admin:User=Depends(require_admin)):
    return [out(p) for p in db.query(GivingPlan).filter(GivingPlan.quarter_id==quarter_id).all()]
@router.post("/{plan_id}/sent")
def mark_sent(plan_id:int, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    p=db.get(GivingPlan,plan_id)
    if not p: raise HTTPException(404,"Plan row not found")
    m=user_member(db,user)
    if not user.is_admin and (not m or p.from_member_id != m.id): raise HTTPException(403,"Can only mark your own sends")
    p.acknowledged=True
    if not db.query(PointsLedger).filter(PointsLedger.quarter_id==p.quarter_id,PointsLedger.from_member_id==p.from_member_id,PointsLedger.to_member_id==p.to_member_id,PointsLedger.amount==p.amount).first():
        db.add(PointsLedger(quarter_id=p.quarter_id,from_member_id=p.from_member_id,to_member_id=p.to_member_id,amount=p.amount,marked_sent_by=user.id))
    db.commit(); return out(p)
