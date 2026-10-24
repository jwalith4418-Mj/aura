"""AURA Engine Monkey & Stress Test Suite.

Runs extensive randomized dry-runs, out-of-order calls, rapid multi-session requests,
and edge cases to verify 100% reliability with zero crashes or unhandled 400 errors.
"""

import sys
import os
import random
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


def test_random_monkey_dsa_loops():
    """Run 25 randomized DSA diagnostic sessions with random answer choices."""
    rng = random.Random(42)
    for i in range(25):
        r = client.post("/api/session/start", json={"domain": "DSA"})
        assert r.status_code == 200
        sid = r.json()["session_id"]

        r = client.post(f"/api/session/{sid}/observe", json={
            "evidence": {
                "timestamp": "2026-08-17T22:10:00+05:30",
                "concept": "binary_search",
                "secondary_concepts": ["boundary_handling"],
                "test_results": {"passed": ["normal_asc"], "failed": ["left_boundary"]},
                "failure_classes": ["left_boundary"],
                "static_pattern": "low_mid_no_increment" if i % 2 == 0 else None,
                "recurrence": i % 3 == 0,
                "code": "while low < high: low = mid",
            }
        })
        assert r.status_code == 200

        r = client.get(f"/api/session/{sid}/diagnose")
        assert r.status_code == 200
        snap = r.json()

        if snap.get("selected_question"):
            q_id = snap["selected_question"]["id"]
            n_opts = len(snap["selected_question"]["options"])
            chosen = rng.randrange(n_opts)
            r = client.post(f"/api/session/{sid}/answer", json={
                "question_id": q_id,
                "option_index": chosen,
            })
            assert r.status_code == 200

        r = client.post(f"/api/session/{sid}/decide")
        assert r.status_code == 200

        r = client.get(f"/api/session/{sid}/retrieve", params={"target": "binary_search", "query": "boundary shrink"})
        assert r.status_code == 200

        r = client.post(f"/api/session/{sid}/teach", json={"target": "binary_search"})
        assert r.status_code == 200

        passed_transfer = rng.choice([True, False])
        original = client.post(
            f"/api/session/{sid}/mark-recovered",
            json={"passed": True, "note": "monkey original reassessment"},
        )
        if original.status_code == 200:
            assert original.json()["gap"]["status"] == "recovered_pending_transfer"
            selected = client.get(f"/api/session/{sid}/transfer-problem")
            assert selected.status_code == 200
            task_data = selected.json()
            if task_data["available"]:
                task = task_data["transfer_problem"]
                r = client.post(
                    f"/api/session/{sid}/verify-transfer",
                    json={
                        "passed": passed_transfer,
                        "note": "monkey transfer result",
                        "transfer_problem_id": task["id"],
                        "original_problem_id": task_data["original_problem_id"],
                        "structurally_different": task_data["structurally_different"],
                    },
                )
                assert r.status_code == 200
                vr = r.json()
                assert "gap" in vr
                assert vr["gap"]["transfer_verified"] is passed_transfer
                assert vr["gap"]["status"] == ("recovered" if passed_transfer else "active_blocker")
            else:
                assert task_data["gap"]["status"] == "recovered_pending_transfer"
                assert task_data["gap"]["transfer_verified"] is False
        else:
            assert original.status_code == 409
            current = client.get(f"/api/session/{sid}/gap").json()["gap"]
            assert current is None or current["status"] != "recovered"

        client.get(f"/api/session/{sid}/map")
        client.get(f"/api/session/{sid}/privacy")

        r = client.post(f"/api/session/{sid}/close")
        assert r.status_code == 200


def test_random_monkey_biology_loops():
    """Run 25 randomized Biology diagnostic sessions with random answer choices."""
    rng = random.Random(123)
    for i in range(25):
        r = client.post("/api/session/start", json={"domain": "Biology"})
        assert r.status_code == 200
        sid = r.json()["session_id"]

        r = client.post(f"/api/session/{sid}/observe", json={
            "evidence": {
                "timestamp": "2026-08-17T13:00:00+05:30",
                "concept": "golgi",
                "secondary_concepts": ["rough_er"],
                "question_id": f"scan_{i}",
                "selected_option": rng.choice([0, 1, 2, 3]),
                "correct_option": 0,
                "distractor_pattern": "attributed_packaging_to_rer",
                "recurrence": True,
                "input_mode": "voice",
            }
        })
        assert r.status_code == 200

        r = client.get(f"/api/session/{sid}/diagnose")
        snap = r.json()

        if snap.get("selected_question"):
            q_id = snap["selected_question"]["id"]
            chosen = rng.randrange(len(snap["selected_question"]["options"]))
            client.post(f"/api/session/{sid}/answer", json={"question_id": q_id, "option_index": chosen})

        client.post(f"/api/session/{sid}/decide")
        client.get(f"/api/session/{sid}/retrieve", params={"target": "golgi", "query": "packages proteins"})
        client.post(f"/api/session/{sid}/teach", json={"target": "golgi"})

        original = client.post(
            f"/api/session/{sid}/mark-recovered",
            json={"passed": True, "note": "monkey biology reassessment"},
        )
        if original.status_code == 200:
            selected = client.get(f"/api/session/{sid}/transfer-problem")
            assert selected.status_code == 200
            task_data = selected.json()
            if task_data["available"]:
                task = task_data["transfer_problem"]
                r = client.post(
                    f"/api/session/{sid}/verify-transfer",
                    json={
                        "passed": True,
                        "transfer_problem_id": task["id"],
                        "original_problem_id": task_data["original_problem_id"],
                        "structurally_different": task_data["structurally_different"],
                        "note": "monkey biology transfer",
                    },
                )
                assert r.status_code == 200
                assert r.json()["gap"]["status"] == "recovered"
                assert r.json()["gap"]["transfer_verified"] is True
            else:
                assert task_data["gap"]["status"] == "recovered_pending_transfer"
                assert task_data["gap"]["transfer_verified"] is False
        else:
            assert original.status_code == 409

        client.post(f"/api/session/{sid}/close")


def test_out_of_order_endpoint_calls():
    """Test out-of-order calls (e.g. verify-transfer directly after start without observe/diagnose/decide)."""
    r = client.post("/api/session/start", json={"domain": "DSA"})
    sid = r.json()["session_id"]

    r = client.post(
        f"/api/session/{sid}/verify-transfer",
        json={
            "passed": True,
            "transfer_problem_id": "bs_practice_first_occurrence",
            "original_problem_id": "unknown-original",
            "structurally_different": True,
            "note": "direct verify should be rejected",
        },
    )
    assert r.status_code == 409
    assert client.get(f"/api/session/{sid}/gap").json()["gap"] is None

    r = client.post(f"/api/session/{sid}/teach", json={"target": "binary_search"})
    assert r.status_code == 200

    r1 = client.post(f"/api/session/{sid}/decide")
    r2 = client.post(f"/api/session/{sid}/decide")
    assert r1.status_code == 200
    assert r2.status_code == 200

    client.post(f"/api/session/{sid}/close")


def test_concurrent_multi_sessions():
    """Interleave requests across 10 simultaneous sessions."""
    sids = []
    for _ in range(10):
        r = client.post("/api/session/start", json={"domain": random.choice(["DSA", "Biology"])})
        sids.append(r.json()["session_id"])

    def worker(sid):
        client.get(f"/api/session/{sid}/state")
        client.get(f"/api/session/{sid}/diagnose")
        client.post(f"/api/session/{sid}/decide")
        client.post(f"/api/session/{sid}/teach", json={"target": "binary_search"})
        # Valid-shaped but out-of-order request must not manufacture a gap.
        client.post(
            f"/api/session/{sid}/verify-transfer",
            json={
                "passed": True,
                "transfer_problem_id": "bs_practice_first_occurrence",
                "original_problem_id": "unknown-original",
                "structurally_different": True,
            },
        )
        client.get(f"/api/session/{sid}/map")
        client.get(f"/api/session/{sid}/privacy")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker, sid) for sid in sids]
        for f in concurrent.futures.as_completed(futures):
            assert f.exception() is None

    for sid in sids:
        client.post(f"/api/session/{sid}/close")


def test_rapid_repeat_requests():
    """Fire rapid repeated calls to diagnose, map, and privacy on a single session."""
    r = client.post("/api/session/start", json={"domain": "DSA"})
    sid = r.json()["session_id"]

    for _ in range(30):
        assert client.get(f"/api/session/{sid}/diagnose").status_code == 200
        assert client.get(f"/api/session/{sid}/map").status_code == 200
        assert client.get(f"/api/session/{sid}/privacy").status_code == 200

    client.post(f"/api/session/{sid}/close")
