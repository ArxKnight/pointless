import random
import time
from types import SimpleNamespace

from typing import Any, cast

from app.services.participant_generator import GenerationSettings, generate_distribution, validate_distribution


def _participants(count: int):
    return [SimpleNamespace(id=i, display_name=f"Participant {i}", is_active=True) for i in range(1, count + 1)]


def _allow_all(participants):
    return [
        SimpleNamespace(from_participant_id=a.id, to_participant_id=b.id, is_allowed=True)
        for a in participants
        for b in participants
        if a.id != b.id
    ]


def test_fourteen_participant_generation_uses_bounded_solver_instead_of_hanging():
    participants = _participants(14)
    rules = _allow_all(participants)
    rng = random.Random(1)
    history = []
    for _ in range(33):
        sender = rng.randint(1, 14)
        recipient = rng.randint(1, 14)
        if sender != recipient:
            history.append({"from_participant_id": sender, "to_participant_id": recipient})

    started = time.perf_counter()
    rows = generate_distribution(cast(Any, participants), cast(Any, rules), GenerationSettings(seed=None), history=history)
    elapsed = time.perf_counter() - started

    assert elapsed < 2
    assert rows
    validate_distribution(rows, cast(Any, participants), cast(Any, rules), GenerationSettings())
