from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CompatibilityGroup, CompatibilityGroupMember, CompatibilityRule, Participant, User
from app.schemas.api import CompatibilityBulkIn, CompatibilityCopyIn, CompatibilityGroupIn, CompatibilityGroupOut, CompatibilityRuleIn, CompatibilityRuleOut
from app.services.auth_service import require_admin
from app.services.audit_service import add_audit_log

router = APIRouter(prefix="/compatibility", tags=["compatibility"])


def ensure_participant(db: Session, participant_id: int) -> Participant:
    p = db.get(Participant, participant_id)
    if not p:
        raise HTTPException(404, f"Participant {participant_id} not found")
    return p


def upsert_rule(db: Session, from_id: int, to_id: int, is_allowed: bool) -> CompatibilityRule | None:
    if from_id == to_id:
        return None
    ensure_participant(db, from_id); ensure_participant(db, to_id)
    rule = db.query(CompatibilityRule).filter_by(from_participant_id=from_id, to_participant_id=to_id).first()
    if not rule:
        rule = CompatibilityRule(from_participant_id=from_id, to_participant_id=to_id, is_allowed=is_allowed)
        db.add(rule)
    else:
        rule.is_allowed = is_allowed
    db.flush()
    return rule


@router.get("/rules", response_model=list[CompatibilityRuleOut])
def list_rules(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(CompatibilityRule).order_by(CompatibilityRule.from_participant_id, CompatibilityRule.to_participant_id).all()


@router.put("/rules", response_model=list[CompatibilityRuleOut])
def set_rule(data: CompatibilityRuleIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    changed = []
    rule = upsert_rule(db, data.from_participant_id, data.to_participant_id, data.is_allowed)
    if rule: changed.append(rule)
    if data.mutual:
        reverse = upsert_rule(db, data.to_participant_id, data.from_participant_id, data.is_allowed)
        if reverse: changed.append(reverse)
    add_audit_log(db, "compatibility_rule_changed", actor=admin, target_type="compatibility", message="Compatibility rule was changed", metadata={"from_participant_id": data.from_participant_id, "to_participant_id": data.to_participant_id, "is_allowed": data.is_allowed, "mutual": data.mutual, "changed_count": len(changed)})
    db.commit()
    return changed


@router.post("/bulk-allow", response_model=list[CompatibilityRuleOut])
def bulk_allow(data: CompatibilityBulkIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    data.is_allowed = True
    return bulk_set(data, db, admin)


@router.post("/bulk-block", response_model=list[CompatibilityRuleOut])
def bulk_block(data: CompatibilityBulkIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    data.is_allowed = False
    return bulk_set(data, db, admin)


def bulk_set(data: CompatibilityBulkIn, db: Session, admin: User):
    changed = []
    for f in data.from_participant_ids:
        for t in data.to_participant_ids:
            rule = upsert_rule(db, f, t, data.is_allowed)
            if rule: changed.append(rule)
            if data.mutual:
                reverse = upsert_rule(db, t, f, data.is_allowed)
                if reverse: changed.append(reverse)
    add_audit_log(db, "compatibility_rule_changed", actor=admin, target_type="compatibility", message="Compatibility rules were changed in bulk", metadata={"from_participant_ids": data.from_participant_ids, "to_participant_ids": data.to_participant_ids, "is_allowed": data.is_allowed, "mutual": data.mutual, "changed_count": len(changed)})
    db.commit()
    return changed


@router.post("/clear")
def clear_rules(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    deleted = db.query(CompatibilityRule).delete()
    add_audit_log(db, "compatibility_rule_changed", actor=admin, target_type="compatibility", message="All compatibility rules were cleared", metadata={"deleted_count": deleted})
    db.commit()
    return {"ok": True}


@router.post("/copy", response_model=list[CompatibilityRuleOut])
def copy_rules(data: CompatibilityCopyIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    ensure_participant(db, data.source_participant_id); ensure_participant(db, data.target_participant_id)
    db.query(CompatibilityRule).filter(CompatibilityRule.from_participant_id == data.target_participant_id).delete()
    copied = []
    for rule in db.query(CompatibilityRule).filter(CompatibilityRule.from_participant_id == data.source_participant_id).all():
        if rule.to_participant_id == data.target_participant_id:
            continue
        copied.append(upsert_rule(db, data.target_participant_id, rule.to_participant_id, rule.is_allowed))
    copied = [r for r in copied if r]
    add_audit_log(db, "compatibility_rule_changed", actor=admin, target_type="compatibility", message="Compatibility rules were copied between participants", metadata={"source_participant_id": data.source_participant_id, "target_participant_id": data.target_participant_id, "copied_count": len(copied)})
    db.commit()
    return copied


def group_out(db: Session, group: CompatibilityGroup) -> dict:
    ids = [m.participant_id for m in db.query(CompatibilityGroupMember).filter_by(group_id=group.id).all()]
    return {"id": group.id, "name": group.name, "notes": group.notes, "participant_ids": ids}


@router.get("/groups", response_model=list[CompatibilityGroupOut])
def list_groups(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [group_out(db, g) for g in db.query(CompatibilityGroup).order_by(CompatibilityGroup.name).all()]


@router.post("/groups", response_model=CompatibilityGroupOut)
def create_group(data: CompatibilityGroupIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    g = CompatibilityGroup(name=data.name.strip(), notes=data.notes)
    db.add(g); db.flush()
    for pid in data.participant_ids:
        ensure_participant(db, pid)
        db.add(CompatibilityGroupMember(group_id=g.id, participant_id=pid))
    add_audit_log(db, "compatibility_rule_changed", actor=admin, target_type="compatibility_group", target_id=g.id, target_name=g.name, message=f"Compatibility group {g.name} was created", metadata={"participant_ids": data.participant_ids})
    db.commit(); db.refresh(g)
    return group_out(db, g)


@router.post("/groups/{group_id}/allow-all", response_model=list[CompatibilityRuleOut])
def allow_group(group_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    group = db.get(CompatibilityGroup, group_id)
    if not group: raise HTTPException(404, "Compatibility group not found")
    ids = [m.participant_id for m in db.query(CompatibilityGroupMember).filter_by(group_id=group.id).all()]
    changed = []
    for a in ids:
        for b in ids:
            r = upsert_rule(db, a, b, True)
            if r: changed.append(r)
    add_audit_log(db, "compatibility_rule_changed", actor=admin, target_type="compatibility_group", target_id=group.id, target_name=group.name, message=f"Compatibility group {group.name} was allowed internally", metadata={"participant_ids": ids, "changed_count": len(changed)})
    db.commit()
    return changed
