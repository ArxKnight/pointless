import random
from collections import defaultdict
from itertools import combinations

ALLOWED_DENOMINATIONS = {5, 10, 15, 20, 25, 30, 40, 50}
_SPLITS = [(a, 50-a) for a in ALLOWED_DENOMINATIONS for _ in [0] if 50-a in ALLOWED_DENOMINATIONS and a not in (0,50) and 50-a not in (0,50)]


def _last_two_indexes(history):
    qs = sorted({h.get("quarter_index", h.get("quarter_id", 0)) for h in history})
    return set(qs[-2:])


def blocked_pairs(history):
    last_two = _last_two_indexes(history)
    by_pair_quarters = defaultdict(set)
    full_50_quarters = defaultdict(set)
    for h in history:
        q = h.get("quarter_index", h.get("quarter_id", 0))
        if q not in last_two:
            continue
        pair = (h["from_member_id"], h["to_member_id"])
        by_pair_quarters[pair].add(q)
        if h["amount"] == 50:
            full_50_quarters[pair].add(q)
    blocked = {pair for pair, qs in by_pair_quarters.items() if len(qs) >= 2}
    blocked |= {pair for pair, qs in full_50_quarters.items() if len(qs) >= 2}
    return blocked


def generate_balanced_plan(members, history=None, seed=None, max_attempts=2000):
    """Return list of dict plan rows satisfying balanced 50 given/received totals.

    Uses a randomised regular directed graph. For N>=3 every giver uses two
    offsets in a shuffled ring, making every member receive one edge of each
    split amount. If constraints make that impossible, retries with new rings.
    """
    history = history or []
    active = [m for m in members if m.get("active", True)]
    ids = [int(m["id"]) for m in active]
    n = len(ids)
    if n < 2:
        raise ValueError("At least two active members are required")
    blocked = blocked_pairs(history)
    rng = random.Random(seed)
    if n == 2:
        a, b = ids
        if (a, b) in blocked or (b, a) in blocked:
            raise ValueError("No valid plan: required two-member pair is blocked")
        return [
            {"from_member_id": a, "to_member_id": b, "amount": 50},
            {"from_member_id": b, "to_member_id": a, "amount": 50},
        ]

    offsets = [(d1, d2) for d1 in range(1, n) for d2 in range(1, n) if d1 != d2]
    for _attempt in range(max_attempts):
        order = ids[:]
        rng.shuffle(order)
        d1, d2 = rng.choice(offsets)
        split = rng.choice(_SPLITS)
        if rng.random() < 0.5:
            split = (split[1], split[0])
        rows = []
        ok = True
        for i, giver in enumerate(order):
            recipients = [order[(i + d1) % n], order[(i + d2) % n]]
            for recipient, amount in zip(recipients, split):
                if giver == recipient or (giver, recipient) in blocked:
                    ok = False
                    break
                rows.append({"from_member_id": giver, "to_member_id": recipient, "amount": amount})
            if not ok:
                break
        if ok:
            validate_plan(rows, active, history)
            return rows
    raise ValueError("No valid balanced plan could be generated with the current history constraints")


def validate_plan(plan, members, history=None):
    ids = {int(m["id"]) for m in members if m.get("active", True)}
    blocked = blocked_pairs(history or [])
    given = defaultdict(int); received = defaultdict(int); recipients = defaultdict(set)
    for row in plan:
        f = row["from_member_id"]; t = row["to_member_id"]; amount = row["amount"]
        if f not in ids or t not in ids: raise ValueError("Plan contains inactive/unknown member")
        if f == t: raise ValueError("Self sends are not allowed")
        if amount not in ALLOWED_DENOMINATIONS: raise ValueError("Invalid denomination")
        if (f, t) in blocked: raise ValueError("Plan uses blocked historical pair")
        given[f] += amount; received[t] += amount; recipients[f].add(t)
    for member_id in ids:
        if given[member_id] != 50: raise ValueError(f"Member {member_id} gives {given[member_id]}, not 50")
        if received[member_id] != 50: raise ValueError(f"Member {member_id} receives {received[member_id]}, not 50")
        if len(ids) > 2 and len(recipients[member_id]) < 2: raise ValueError("Minimum split rule failed")
    return True
