from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user
from app.services.analytics_service import overview, heatmap, quarter_breakdown
router=APIRouter(prefix="/analytics", tags=["analytics"])
@router.get("/overview")
def get_overview(db:Session=Depends(get_db), user:User=Depends(get_current_user)): return overview(db)
@router.get("/heatmap")
def get_heatmap(db:Session=Depends(get_db), user:User=Depends(get_current_user)): return heatmap(db)
@router.get("/quarters")
def quarters(db:Session=Depends(get_db), user:User=Depends(get_current_user)): return quarter_breakdown(db)
