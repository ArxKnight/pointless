from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DepartmentMember, GivingPlan, PointsLedger, Quarter, User
from app.schemas.api import GenerateIn, QuarterOut
from app.services.auth_service import require_admin
from app.services.plan_generator import generate_balanced_plan, validate_plan

router=APIRouter(prefix="/quarters", tags=["quarters"])
def next_quarter(db):
    last=db.query(Quarter).order_by(Quarter.year.desc(), Quarter.quarter.desc()).first()
    if not last:
        now=datetime.utcnow(); return now.year, ((now.month-1)//3)+1
    return (last.year+1,1) if last.quarter==4 else (last.year,last.quarter+1)
def plan_rows(db,qid):
    rows=db.query(GivingPlan).filter(GivingPlan.quarter_id==qid).all(); return [{"id":p.id,"quarter_id":p.quarter_id,"from_member_id":p.from_member_id,"to_member_id":p.to_member_id,"from_name":p.from_member.display_name,"to_name":p.to_member.display_name,"amount":p.amount,"acknowledged":p.acknowledged} for p in rows]
@router.get("", response_model=list[QuarterOut])
def list_quarters(db:Session=Depends(get_db), admin:User=Depends(require_admin)): return db.query(Quarter).order_by(Quarter.year.desc(),Quarter.quarter.desc()).all()
@router.post("/generate")
def generate(data:GenerateIn, db:Session=Depends(get_db), admin:User=Depends(require_admin)):
    y,q=(data.year,data.quarter) if data.year and data.quarter else next_quarter(db)
    existing=db.query(Quarter).filter(Quarter.year==y,Quarter.quarter==q).first()
    if existing and db.query(PointsLedger).filter(PointsLedger.quarter_id==existing.id).first(): raise HTTPException(409,"Cannot regenerate after sends are marked")
    members=db.query(DepartmentMember).filter(DepartmentMember.active==True).order_by(DepartmentMember.id).all()
    hist=[]
    for p in db.query(GivingPlan).join(Quarter).order_by(Quarter.year,Quarter.quarter).all(): hist.append({"quarter_id":p.quarter_id,"quarter_index":p.quarter.year*4+p.quarter.quarter,"from_member_id":p.from_member_id,"to_member_id":p.to_member_id,"amount":p.amount})
    plan=generate_balanced_plan([{"id":m.id,"display_name":m.display_name,"active":m.active} for m in members], hist, seed=data.seed)
    if data.preview: return {"quarter":{"year":y,"quarter":q,"label":f"Q{q} {y}"},"plan":plan}
    for old in db.query(Quarter).filter(Quarter.is_active==True): old.is_active=False
    if existing:
        db.query(GivingPlan).filter(GivingPlan.quarter_id==existing.id).delete(); quarter=existing; quarter.is_active=True; quarter.is_completed=False; quarter.generated_at=datetime.utcnow()
    else:
        quarter=Quarter(year=y,quarter=q,label=f"Q{q} {y}",is_active=True,is_completed=False); db.add(quarter); db.flush()
    for r in plan: db.add(GivingPlan(quarter_id=quarter.id, **r))
    db.commit(); return {"quarter":QuarterOut.model_validate(quarter),"plan":plan_rows(db,quarter.id)}
@router.get("/{quarter_id}")
def detail(quarter_id:int, db:Session=Depends(get_db), admin:User=Depends(require_admin)):
    q=db.get(Quarter,quarter_id)
    if not q: raise HTTPException(404,"Quarter not found")
    return {"quarter":QuarterOut.model_validate(q),"plan":plan_rows(db,q.id)}
@router.post("/{quarter_id}/complete")
def complete(quarter_id:int, db:Session=Depends(get_db), admin:User=Depends(require_admin)):
    q=db.get(Quarter,quarter_id)
    if not q: raise HTTPException(404,"Quarter not found")
    q.is_active=False; q.is_completed=True; db.commit(); return {"ok":True}
