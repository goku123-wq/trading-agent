from datetime import datetime

from agent import clock


def ist(*a):
    return datetime(*a, tzinfo=clock.IST)


def test_morning_jobs_due_once():
    now = ist(2026, 9, 28, 8, 40)  # Monday
    assert [j for j, _ in clock.due(now, {})] == ["ask"]
    done = {k: True for _, k in clock.due(now, {})}
    assert clock.due(ist(2026, 9, 28, 8, 45), done) == []
    assert clock.due(ist(2026, 9, 28, 9, 30), {}) and clock.due(ist(2026, 9, 28, 9, 30), {})[0][0] == "stop-check.yml"


def test_stop_slots_and_weekend():
    a = clock.due(ist(2026, 9, 28, 9, 16), {})
    b = clock.due(ist(2026, 9, 28, 9, 26), {})
    assert a[0][1] != b[0][1]
    assert clock.due(ist(2026, 9, 28, 15, 45), {}) == []
    assert clock.due(ist(2026, 9, 26, 10, 0), {}) == []  # Saturday
    assert [j for j, _ in clock.due(ist(2026, 9, 27, 9, 0), {})] == ["update-universe.yml"]  # Sunday


def test_prune():
    done = {"ask@2026-09-20": True, "ask@2026-09-28": True, "stop-check.yml@2026-09-28#3": True}
    assert set(clock.prune(done, ist(2026, 9, 28, 9))) == {"ask@2026-09-28", "stop-check.yml@2026-09-28#3"}
