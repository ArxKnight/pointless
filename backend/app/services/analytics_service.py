from collections import defaultdict
from sqlalchemy.orm import Session
from app.models import DepartmentMember, GivingPlan, PointsLedger, Quarter

def overview(db: Session):
    q = db.query(Quarter).filter(Quarter.is_active == True, Quarter.is_completed == False).order_by(Quarter.id.desc()).first()
    member_count = db.query(DepartmentMember).filter(DepartmentMember.active == True).count()
    if not q: return {"total_members": member_count, "active_quarter": None, "completion_rate": 0, "total_sent":0, "total_planned":0}
    planned = db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).all()
    sent = [p for p in planned if p.acknowledged]
    return {"total_members": member_count, "active_quarter": q.label, "completion_rate": (len(sent)/len(planned)*100 if planned else 0), "total_sent": sum(p.amount for p in sent), "total_planned": sum(p.amount for p in planned)}

def heatmap(db: Session):
    members = db.query(DepartmentMember).order_by(DepartmentMember.display_name).all()
    plans = db.query(GivingPlan).all()
    matrix = defaultdict(int)
    for p in plans: matrix[f"{p.from_member_id}:{p.to_member_id}"] += p.amount
    return {"members":[{"id":m.id,"name":m.display_name} for m in members], "matrix":matrix}

def quarter_breakdown(db: Session):
    rows=[]
    for q in db.query(Quarter).order_by(Quarter.year, Quarter.quarter).all():
        given=defaultdict(int); received=defaultdict(int); sent=defaultdict(int)
        for p in db.query(GivingPlan).filter(GivingPlan.quarter_id==q.id):
            given[p.from_member_id]+=p.amount; received[p.to_member_id]+=p.amount
            if p.acknowledged: sent[p.from_member_id]+=p.amount
        rows.append({"quarter":q.label,"given":given,"received":received,"sent":sent})
    return rows
