from collections import defaultdict

from app.services.plan_generator import generate_balanced_plan, validate_plan, ALLOWED_DENOMINATIONS


def members(n):
    return [{"id": i + 1, "display_name": f"Member {i+1}"} for i in range(n)]


def totals(plan):
    given = defaultdict(int)
    received = defaultdict(int)
    for row in plan:
        given[row["from_member_id"]] += row["amount"]
        received[row["to_member_id"]] += row["amount"]
    return given, received


def test_generates_balanced_valid_plan_for_ten_members():
    plan = generate_balanced_plan(members(10), history=[], seed=42)
    given, received = totals(plan)
    assert set(given) == set(range(1, 11))
    assert set(received) == set(range(1, 11))
    assert all(total == 50 for total in given.values())
    assert all(total == 50 for total in received.values())
    assert all(row["amount"] in ALLOWED_DENOMINATIONS for row in plan)
    assert all(row["from_member_id"] != row["to_member_id"] for row in plan)
    for giver in range(1, 11):
        assert len({r["to_member_id"] for r in plan if r["from_member_id"] == giver}) >= 2
    validate_plan(plan, members(10), history=[])


def test_blocks_recipient_used_in_previous_two_quarters():
    history = [
        {"quarter_index": 1, "from_member_id": 1, "to_member_id": 2, "amount": 25},
        {"quarter_index": 2, "from_member_id": 1, "to_member_id": 2, "amount": 25},
    ]
    for seed in range(20):
        plan = generate_balanced_plan(members(6), history=history, seed=seed)
        assert not any(r["from_member_id"] == 1 and r["to_member_id"] == 2 for r in plan)
        validate_plan(plan, members(6), history=history)


def test_blocks_third_repeated_full_50_send_even_for_two_member_group():
    history = [
        {"quarter_index": 1, "from_member_id": 1, "to_member_id": 2, "amount": 50},
        {"quarter_index": 2, "from_member_id": 1, "to_member_id": 2, "amount": 50},
    ]
    try:
        generate_balanced_plan(members(2), history=history, seed=1)
    except ValueError as exc:
        assert "No valid" in str(exc) or "blocked" in str(exc)
    else:
        raise AssertionError("expected impossible two-member blocked plan to fail")


def test_three_member_group_balances_with_two_recipients_each():
    plan = generate_balanced_plan(members(3), history=[], seed=7)
    given, received = totals(plan)
    assert all(total == 50 for total in given.values())
    assert all(total == 50 for total in received.values())
    for giver in range(1, 4):
        assert len({r["to_member_id"] for r in plan if r["from_member_id"] == giver}) == 2
