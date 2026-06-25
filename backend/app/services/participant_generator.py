import random
from collections import defaultdict, deque
from dataclasses import dataclass, field

from app.models import CompatibilityRule, Participant

POINTS_PER_PARTICIPANT = 50


@dataclass
class GenerationSettings:
    min_amount: int = 5
    max_amount: int = 25
    preferred_min_recipients: int = 2
    preferred_max_recipients: int = 5
    seed: int | None = None
    default_allowed: bool = False


@dataclass
class FeasibilityResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_allowed_edges(participants: list[Participant], rules: list[CompatibilityRule], default_allowed: bool = False) -> set[tuple[int, int]]:
    ids = {p.id for p in participants}
    edges = {(a, b) for a in ids for b in ids if a != b and default_allowed}
    for rule in rules:
        pair = (rule.from_participant_id, rule.to_participant_id)
        if rule.from_participant_id not in ids or rule.to_participant_id not in ids or rule.from_participant_id == rule.to_participant_id:
            continue
        if rule.is_allowed:
            edges.add(pair)
        else:
            edges.discard(pair)
    return edges


def validate_feasibility(participants: list[Participant], rules: list[CompatibilityRule], settings: GenerationSettings | None = None, default_allowed: bool | None = None) -> FeasibilityResult:
    settings = settings or GenerationSettings()
    if default_allowed is not None:
        settings.default_allowed = default_allowed
    active = [p for p in participants if p.is_active]
    errors: list[str] = []
    if len(active) < 2:
        errors.append("At least two active participants are required.")
        return FeasibilityResult(False, errors)
    if settings.min_amount <= 0 or settings.max_amount <= 0 or settings.min_amount > settings.max_amount:
        errors.append("Minimum and maximum allocation settings are invalid.")
    if POINTS_PER_PARTICIPANT % 1 != 0:
        errors.append("Point total must be a whole number.")
    ids = {p.id for p in active}
    edges = build_allowed_edges(active, rules, settings.default_allowed)
    for p in active:
        outgoing = [b for a, b in edges if a == p.id]
        incoming = [a for a, b in edges if b == p.id]
        if not outgoing:
            errors.append(f"{p.display_name} has no eligible recipients.")
        if not incoming:
            errors.append(f"{p.display_name} has no eligible givers.")
        if outgoing and len(outgoing) * settings.max_amount < POINTS_PER_PARTICIPANT:
            errors.append(f"{p.display_name} cannot send 50 points with the current maximum allocation.")
        if incoming and len(incoming) * settings.max_amount < POINTS_PER_PARTICIPANT:
            errors.append(f"{p.display_name} cannot receive 50 points with the current maximum allocation.")
    if settings.preferred_min_recipients * settings.min_amount > POINTS_PER_PARTICIPANT:
        errors.append("Preferred minimum recipients and minimum allocation cannot sum to 50.")
    if settings.preferred_max_recipients * settings.max_amount < POINTS_PER_PARTICIPANT:
        errors.append("Preferred maximum recipients and maximum allocation cannot sum to 50.")
    return FeasibilityResult(not errors, errors)


def _candidate_splits(settings: GenerationSettings, n: int) -> list[list[int]]:
    base = [25, 15, 10] if n >= 4 else [25, 25]
    if n >= 5:
        base = [20, 15, 10, 5]
    variants = [base]
    if n >= 4:
        variants += [[25, 10, 10, 5], [20, 20, 5, 5], [25, 15, 5, 5]]
    clean = []
    for split in variants:
        split = [x for x in split if settings.min_amount <= x <= settings.max_amount]
        if sum(split) == POINTS_PER_PARTICIPANT and len(split) <= n - 1:
            clean.append(split)
    return clean or [[POINTS_PER_PARTICIPANT]]


def _ring_plan(participants: list[Participant], edges: set[tuple[int, int]], settings: GenerationSettings) -> list[dict] | None:
    rng = random.Random(settings.seed)
    ids = [p.id for p in participants]
    if len(ids) < 3:
        return None
    splits = _candidate_splits(settings, len(ids))
    for _ in range(700):
        order = ids[:]
        rng.shuffle(order)
        split = rng.choice(splits)
        offsets = list(range(1, len(ids)))
        rng.shuffle(offsets)
        offsets = offsets[: len(split)]
        rows = []
        ok = True
        for i, giver in enumerate(order):
            for offset, amount in zip(offsets, split):
                recipient = order[(i + offset) % len(order)]
                if (giver, recipient) not in edges:
                    ok = False
                    break
                rows.append({"from_participant_id": giver, "to_participant_id": recipient, "amount": amount})
            if not ok:
                break
        if ok:
            return rows
    return None


def _max_flow_plan(participants: list[Participant], edges: set[tuple[int, int]], settings: GenerationSettings) -> list[dict]:
    unit = settings.min_amount
    if POINTS_PER_PARTICIPANT % unit != 0 or settings.max_amount % unit != 0:
        unit = 1
    need = POINTS_PER_PARTICIPANT // unit
    cap = settings.max_amount // unit
    rng = random.Random(settings.seed)
    senders = [f"s:{p.id}" for p in participants]
    recipients = [f"r:{p.id}" for p in participants]
    source, sink = "source", "sink"
    graph: dict[str, dict[str, int]] = defaultdict(dict)

    def add(u, v, c):
        graph[u][v] = graph[u].get(v, 0) + c
        graph[v].setdefault(u, 0)

    for p in participants:
        add(source, f"s:{p.id}", need)
        add(f"r:{p.id}", sink, need)
    edge_list = list(edges)
    rng.shuffle(edge_list)
    for a, b in edge_list:
        add(f"s:{a}", f"r:{b}", cap)

    flow = 0
    parent: dict[str, str] = {}
    while True:
        parent.clear()
        q = deque([source])
        parent[source] = ""
        while q and sink not in parent:
            u = q.popleft()
            neighbors = list(graph[u].keys())
            rng.shuffle(neighbors)
            for v in neighbors:
                if v not in parent and graph[u][v] > 0:
                    parent[v] = u
                    q.append(v)
        if sink not in parent:
            break
        inc = 10**9
        v = sink
        while v != source:
            u = parent[v]
            inc = min(inc, graph[u][v])
            v = u
        v = sink
        while v != source:
            u = parent[v]
            graph[u][v] -= inc
            graph[v][u] = graph[v].get(u, 0) + inc
            v = u
        flow += inc

    if flow != need * len(participants):
        raise ValueError("Unable to ensure every participant receives 50 points with the current compatibility rules.")

    rows = []
    for a, b in edges:
        used = graph[f"r:{b}"].get(f"s:{a}", 0)
        if used > 0:
            amount = used * unit
            rows.append({"from_participant_id": a, "to_participant_id": b, "amount": amount})
    return rows


def generate_distribution(participants: list[Participant], rules: list[CompatibilityRule], settings: GenerationSettings | None = None, history: list[dict] | None = None) -> list[dict]:
    settings = settings or GenerationSettings()
    active = [p for p in participants if p.is_active]
    feasibility = validate_feasibility(active, rules, settings)
    if not feasibility.valid:
        raise ValueError("Unable to generate this distribution. " + " ".join(feasibility.errors))
    edges = build_allowed_edges(active, rules, settings.default_allowed)
    plan = _ring_plan(active, edges, settings)
    if plan is None:
        plan = _max_flow_plan(active, edges, settings)
    validate_distribution(plan, active, rules, settings)
    return sorted(plan, key=lambda r: (r["from_participant_id"], r["to_participant_id"]))


def validate_distribution(plan: list[dict], participants: list[Participant], rules: list[CompatibilityRule], settings: GenerationSettings | None = None) -> bool:
    settings = settings or GenerationSettings()
    ids = {p.id for p in participants if p.is_active}
    edges = build_allowed_edges([p for p in participants if p.is_active], rules, settings.default_allowed)
    sent = defaultdict(int)
    received = defaultdict(int)
    pairs = set()
    for row in plan:
        f = int(row["from_participant_id"])
        t = int(row["to_participant_id"])
        amount = int(row["amount"])
        if f not in ids or t not in ids:
            raise ValueError("Plan contains an unknown or inactive participant.")
        if f == t:
            raise ValueError("A participant cannot give points to themselves.")
        if (f, t) not in edges:
            raise ValueError("Plan uses a blocked or missing compatibility rule.")
        if amount <= 0 or amount != row["amount"]:
            raise ValueError("Allocation amounts must be positive whole numbers.")
        if amount < settings.min_amount or amount > settings.max_amount:
            raise ValueError("Allocation amount is outside the configured minimum/maximum.")
        if (f, t) in pairs:
            raise ValueError("Duplicate allocation pair in plan.")
        pairs.add((f, t))
        sent[f] += amount
        received[t] += amount
    for p in ids:
        if sent[p] != POINTS_PER_PARTICIPANT:
            raise ValueError(f"Participant {p} sends {sent[p]}, not 50.")
        if received[p] != POINTS_PER_PARTICIPANT:
            raise ValueError(f"Participant {p} receives {received[p]}, not 50.")
    return True
