from sqlalchemy.orm import Session
from app.models import Team, TeamGroup

INITIAL_TEAM_GROUPS = [
    ("Shift A + Shift B", "Initial sharing group for teams that commonly share points.", 10),
    ("Shift C + Shift D", "Initial sharing group for teams that commonly share points.", 20),
    ("Others", "Independent initial group.", 30),
]
INITIAL_TEAMS = [
    ("Shift A", "Shift A initial team.", "#2563eb", 10, "Shift A + Shift B"),
    ("Shift B", "Shift B initial team.", "#7c3aed", 20, "Shift A + Shift B"),
    ("Shift C", "Shift C initial team.", "#059669", 30, "Shift C + Shift D"),
    ("Shift D", "Shift D initial team.", "#ea580c", 40, "Shift C + Shift D"),
    ("Others", "Independent or non-shift users.", "#64748b", 50, "Others"),
]


def ensure_initial_team_data(db: Session) -> None:
    """Create initial team/group records if absent; never creates or guesses users."""
    groups: dict[str, TeamGroup] = {}
    for name, description, order in INITIAL_TEAM_GROUPS:
        group = db.query(TeamGroup).filter(TeamGroup.name == name).first()
        if not group:
            group = TeamGroup(name=name, description=description, display_order=order, is_active=True)
            db.add(group)
            db.flush()
        groups[name] = group

    for name, description, colour, order, group_name in INITIAL_TEAMS:
        team = db.query(Team).filter(Team.name == name).first()
        if not team:
            db.add(Team(
                name=name,
                description=description,
                colour=colour,
                display_order=order,
                is_active=True,
                group_id=groups[group_name].id,
            ))
    db.commit()
