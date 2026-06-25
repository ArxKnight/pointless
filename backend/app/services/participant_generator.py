import itertools
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field

from app.models import CompatibilityRule, Participant

POINTS_PER_PARTICIPANT = 50
PERMITTED_AMOUNTS = (10, 15, 20, 25, 30, 40, 45, 50)
ZERO_OR_PERMITTED_AMOUNTS = (0,) + PERMITTED_AMOUNTS
# 45 remains a permitted individual value for future configurations, but no
# positive permitted value can complete 45 to 50, so these are the usable split
# patterns for the current 50-point target.
VALID_SPLIT_PATTERNS = tuple(
    tuple(p) for p in {
        (50,),
        (40, 10),
        (30, 20),
        (30, 10, 10),
        (25, 25),
        (25, 15, 10),
        (20, 20, 10),
        (20, 15, 15),
        (15, 15, 10, 10),
        (10, 10, 10, 10, 10),
    }
)


@dataclass
class GenerationSettings:
    min_amount: int = 10
    max_amount: int = 50
    preferred_min_recipients: int = 2
    preferred_max_recipients: int = 3
    seed: int | None = None
    default_allowed: bool = False


@dataclass
class FeasibilityResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def usable_amounts(settings: GenerationSettings | None = None) -> tuple[int, ...]:
    settings = settings or GenerationSettings()
    return tuple(a for a in PERMITTED_AMOUNTS if settings.min_amount <= a <= settings.max_amount)


def split_patterns(settings: GenerationSettings | None = None) -> list[tuple[int, ...]]:
    amounts = set(usable_amounts(settings))
    patterns = [p for p in VALID_SPLIT_PATTERNS if all(a in amounts for a in p)]
    return sorted(patterns, key=lambda p: (_pattern_penalty(p), len(p), p))


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


def _component_errors(participants: list[Participant], edges: set[tuple[int, int]]) -> list[str]:
    """Find weakly disconnected selected components; each must balance internally."""
    by_id = {p.id: p for p in participants}
    neighbors: dict[int, set[int]] = {p.id: set() for p in participants}
    for a, b in edges:
        neighbors[a].add(b); neighbors[b].add(a)
    seen: set[int] = set(); errors: list[str] = []
    for pid in by_id:
        if pid in seen:
            continue
        q = deque([pid]); seen.add(pid); comp = []
        while q:
            cur = q.popleft(); comp.append(cur)
            for nxt in neighbors[cur]:
                if nxt not in seen:
                    seen.add(nxt); q.append(nxt)
        if len(comp) == 1 and len(participants) > 1:
            errors.append(f"The selected compatibility component containing {by_id[comp[0]].display_name} cannot be balanced.")
    return errors


def validate_feasibility(participants: list[Participant], rules: list[CompatibilityRule], settings: GenerationSettings | None = None, default_allowed: bool | None = None) -> FeasibilityResult:
    settings = settings or GenerationSettings()
    if default_allowed is not None:
        settings.default_allowed = default_allowed
    active = [p for p in participants if p.is_active]
    errors: list[str] = []
    warnings: list[str] = []
    if len(active) < 2:
        errors.append("At least two active participants are required.")
        return FeasibilityResult(False, errors)
    if not split_patterns(settings):
        errors.append("The permitted allocation values cannot produce an exact 50-point total.")
    amounts = usable_amounts(settings)
    if 45 in amounts:
        warnings.append("45 is configured as permitted but cannot be used in any valid 50-point split without a 5-point remainder, so generation will not use it.")
    edges = build_allowed_edges(active, rules, settings.default_allowed)
    for p in active:
        outgoing = [b for a, b in edges if a == p.id]
        incoming = [a for a, b in edges if b == p.id]
        if not outgoing:
            errors.append(f"{p.display_name} has no eligible recipients.")
        if not incoming:
            errors.append(f"{p.display_name} has no eligible senders.")
        if outgoing and len(outgoing) < min(len(pattern) for pattern in split_patterns(settings)):
            pass
        if outgoing and not any(len(pattern) <= len(outgoing) for pattern in split_patterns(settings)):
            errors.append(f"{p.display_name} cannot send exactly 50 points using the permitted allocation values and eligible recipients.")
        if incoming and not any(len(pattern) <= len(incoming) for pattern in split_patterns(settings)):
            errors.append(f"The current compatibility rules cannot provide {p.display_name} with exactly 50 incoming points using the permitted allocation values.")
    errors.extend(_component_errors(active, edges))
    return FeasibilityResult(not errors, errors, warnings)


def _pattern_penalty(pattern: tuple[int, ...]) -> int:
    penalty = 0
    if pattern == (50,): penalty += 90
    if sorted(pattern) == [25, 25]: penalty += 60
    if len(pattern) == 1: penalty += 40
    if len(pattern) in (2, 3): penalty -= 20
    if len(set(pattern)) == 1: penalty += 20
    return penalty


def _candidate_rows_for_sender(sender: Participant, participants: list[Participant], edges: set[tuple[int, int]], remaining_in: dict[int, int], rng: random.Random, history_pairs: set[tuple[int, int]], existing_rows: list[dict], settings: GenerationSettings | None = None) -> list[list[dict]]:
    recipients = [p.id for p in participants if (sender.id, p.id) in edges and remaining_in.get(p.id, 0) > 0]
    candidates: list[tuple[int, list[dict]]] = []
    used_reverse = {(r["to_participant_id"], r["from_participant_id"]) for r in existing_rows}
    patterns = split_patterns(settings)
    rng.shuffle(patterns)
    for pattern in patterns:
        if len(pattern) > len(recipients):
            continue
        # Use a bounded shuffled subset of combinations to avoid explosive search on larger teams.
        combos = list(itertools.combinations(recipients, len(pattern)))
        rng.shuffle(combos)
        for combo in combos[:160]:
            perms = set(itertools.permutations(pattern, len(pattern)))
            perms = list(perms); rng.shuffle(perms)
            for amounts in perms:
                if any(remaining_in[to] < amount for to, amount in zip(combo, amounts)):
                    continue
                rows = [{"from_participant_id": sender.id, "to_participant_id": to, "amount": amount} for to, amount in zip(combo, amounts)]
                recipient_set = {r["to_participant_id"] for r in rows}
                reciprocal = sum(1 for r in rows if (sender.id, r["to_participant_id"]) in used_reverse)
                repeated = sum(1 for r in rows if (sender.id, r["to_participant_id"]) in history_pairs)
                score = _pattern_penalty(tuple(sorted(amounts, reverse=True))) + reciprocal * 12 + repeated * 10
                # Prefer sender choices that do not exactly mirror incoming partner set.
                if len(recipient_set) == len(rows) and reciprocal == len(rows):
                    score += 25
                score += rng.randint(0, 18)
                candidates.append((score, rows))
    candidates.sort(key=lambda item: item[0])
    return [rows for _, rows in candidates[:220]]


def _recent_history_pairs(history: list[dict] | None) -> set[tuple[int, int]]:
    pairs = set()
    for row in history or []:
        f = row.get("from_participant_id") or row.get("from_member_id")
        t = row.get("to_participant_id") or row.get("to_member_id")
        if f and t:
            pairs.add((int(f), int(t)))
    return pairs


def generate_distribution(participants: list[Participant], rules: list[CompatibilityRule], settings: GenerationSettings | None = None, history: list[dict] | None = None) -> list[dict]:
    settings = settings or GenerationSettings()
    active = [p for p in participants if p.is_active]
    feasibility = validate_feasibility(active, rules, settings)
    if not feasibility.valid:
        raise ValueError("Unable to generate a valid distribution. " + " ".join(feasibility.errors))
    edges = build_allowed_edges(active, rules, settings.default_allowed)
    rng = random.Random(settings.seed)
    history_pairs = _recent_history_pairs(history)
    # Harder senders first: those with fewer eligible recipients/incoming capacity.
    sender_order = active[:]
    sender_order.sort(key=lambda p: (sum(1 for a, _ in edges if a == p.id), rng.random()))
    remaining_in = {p.id: POINTS_PER_PARTICIPANT for p in active}
    rows: list[dict] = []

    def backtrack(index: int) -> bool:
        if index == len(sender_order):
            return all(v == 0 for v in remaining_in.values())
        sender = sender_order[index]
        candidates = _candidate_rows_for_sender(sender, active, edges, remaining_in, rng, history_pairs, rows, settings)
        for candidate in candidates:
            for r in candidate:
                remaining_in[r["to_participant_id"]] -= r["amount"]
            rows.extend(candidate)
            # Prune: every future recipient with remaining need must still have a future sender.
            future_senders = {p.id for p in sender_order[index + 1:]}
            possible = True
            for pid, need in remaining_in.items():
                if need > 0 and not any((sid, pid) in edges for sid in future_senders):
                    possible = False; break
            if possible and backtrack(index + 1):
                return True
            del rows[-len(candidate):]
            for r in candidate:
                remaining_in[r["to_participant_id"]] += r["amount"]
        return False

    # Try several deterministic order variants; bounded, no unbounded random retry.
    for attempt in range(8):
        if attempt:
            rng.shuffle(sender_order)
            remaining_in = {p.id: POINTS_PER_PARTICIPANT for p in active}
            rows.clear()
        if backtrack(0):
            validate_distribution(rows, active, rules, settings)
            return sorted(rows, key=lambda r: (r["from_participant_id"], r["to_participant_id"]))
    raise ValueError("Unable to generate a valid distribution because the current compatibility graph cannot be balanced with the permitted allocation values.")


def validate_distribution(plan: list[dict], participants: list[Participant], rules: list[CompatibilityRule], settings: GenerationSettings | None = None) -> bool:
    settings = settings or GenerationSettings()
    ids = {p.id for p in participants if p.is_active}
    edges = build_allowed_edges([p for p in participants if p.is_active], rules, settings.default_allowed)
    permitted = set(PERMITTED_AMOUNTS)
    sent = defaultdict(int); received = defaultdict(int); pairs = set()
    for row in plan:
        f = int(row["from_participant_id"]); t = int(row["to_participant_id"]); amount = int(row["amount"])
        if f not in ids or t not in ids:
            raise ValueError("Plan contains an unknown or inactive participant.")
        if f == t:
            raise ValueError("A participant cannot give points to themselves.")
        if (f, t) not in edges:
            raise ValueError("Plan uses a blocked or missing compatibility rule.")
        if amount not in permitted:
            raise ValueError(f"Allocation amount {amount} is not one of the permitted values: {', '.join(map(str, PERMITTED_AMOUNTS))}.")
        if amount < settings.min_amount or amount > settings.max_amount:
            raise ValueError("Allocation amount is outside the configured minimum/maximum.")
        if (f, t) in pairs:
            raise ValueError("Duplicate allocation pair in plan.")
        pairs.add((f, t)); sent[f] += amount; received[t] += amount
    for p in ids:
        if sent[p] != POINTS_PER_PARTICIPANT:
            raise ValueError(f"Participant {p} sends {sent[p]}, not 50.")
        if received[p] != POINTS_PER_PARTICIPANT:
            raise ValueError(f"Participant {p} receives {received[p]}, not 50.")
    return True
