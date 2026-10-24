"""Integration tests for the AURA API — complete learning loop coverage."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from server.main import app
import server.main as server_main
from server.session_manager import session_manager
from adaptive.types import GAP_RECOVERED_PENDING_TRANSFER, LearningGap

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["engine"] == "AURA"


def test_domains():
    r = client.get("/api/domains")
    assert r.status_code == 200
    names = [d["name"] for d in r.json()["domains"]]
    assert "DSA" in names
    assert "Biology" in names


def test_invalid_domain():
    r = client.post("/api/session/start", json={"domain": "nonexistent"})
    assert r.status_code == 400


def test_session_not_found():
    r = client.get("/api/session/fake-id/state")
    assert r.status_code == 404


def test_complete_dsa_loop():
    r = client.post("/api/session/start", json={"domain": "DSA"})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert r.json()["seeded_events"] == 2

    r = client.get(f"/api/session/{sid}/state")
    assert r.status_code == 200
    concepts = r.json()["concepts"]
    assert "binary_search" in concepts

    r = client.post(f"/api/session/{sid}/observe", json={
        "evidence": {
            "timestamp": "2026-08-17T22:10:00+05:30",
            "concept": "binary_search",
            "secondary_concepts": ["boundary_handling"],
            "test_results": {"passed": ["normal_asc", "normal_desc"], "failed": ["left_boundary", "single_element"]},
            "failure_classes": ["left_boundary", "single_element"],
            "static_pattern": "low_mid_no_increment",
            "recurrence": True,
            "code": "while low < high:\n    mid = (low + high) // 2\n    if arr[mid] < target:\n        low = mid\n    else:\n        high = mid",
        }
    })
    assert r.status_code == 200

    r = client.get(f"/api/session/{sid}/diagnose")
    assert r.status_code == 200
    snap = r.json()
    assert "entropy" in snap
    assert len(snap["hypotheses"]) > 0

    q = snap.get("selected_question")
    if q:
        q_id = q["id"]
        r = client.post(f"/api/session/{sid}/answer", json={
            "question_id": q_id,
            "option_index": 2,
        })
        assert r.status_code == 200

    r = client.post(f"/api/session/{sid}/decide")
    assert r.status_code == 200

    r = client.get(f"/api/session/{sid}/retrieve", params={"target": "binary_search", "query": "boundary interval shrink"})
    assert r.status_code == 200

    r = client.post(f"/api/session/{sid}/teach", json={"target": "binary_search"})
    assert r.status_code == 200

    # Transfer cannot skip the explicit original-problem reassessment.
    transfer_early = client.post(
        f"/api/session/{sid}/verify-transfer",
        json={
            "passed": True,
            "transfer_problem_id": "bs_practice_first_occurrence",
            "original_problem_id": "not-yet-confirmed",
            "structurally_different": True,
        },
    )
    assert transfer_early.status_code == 409
    before_reassessment = client.get(f"/api/session/{sid}/gap").json()["gap"]
    assert before_reassessment["status"] == "intervention_applied"
    assert before_reassessment["transfer_verified"] is False

    r = client.post(
        f"/api/session/{sid}/mark-recovered",
        json={"passed": True, "note": "Original problem reassessment passed"},
    )
    assert r.status_code == 200
    assert r.json()["gap"]["status"] == "recovered_pending_transfer"

    task_response = client.get(f"/api/session/{sid}/transfer-problem")
    assert task_response.status_code == 200
    task_data = task_response.json()
    assert task_data["available"] is True
    transfer_task = task_data["transfer_problem"]

    missing_confirmation = client.post(
        f"/api/session/{sid}/verify-transfer",
        json={
            "passed": True,
            "transfer_problem_id": transfer_task["id"],
            "original_problem_id": task_data["original_problem_id"],
            "structurally_different": False,
        },
    )
    assert missing_confirmation.status_code == 400
    unchanged = client.get(f"/api/session/{sid}/gap").json()["gap"]
    assert unchanged["status"] == "recovered_pending_transfer"
    assert unchanged["transfer_verified"] is False

    invalid_selection = client.post(
        f"/api/session/{sid}/verify-transfer",
        json={
            "passed": True,
            "transfer_problem_id": "not-the-selected-task",
            "original_problem_id": task_data["original_problem_id"],
            "structurally_different": True,
        },
    )
    assert invalid_selection.status_code == 400
    unchanged = client.get(f"/api/session/{sid}/gap").json()["gap"]
    assert unchanged["status"] == "recovered_pending_transfer"
    assert unchanged["transfer_verified"] is False

    r = client.post(
        f"/api/session/{sid}/verify-transfer",
        json={
            "passed": True,
            "transfer_problem_id": transfer_task["id"],
            "original_problem_id": task_data["original_problem_id"],
            "structurally_different": task_data["structurally_different"],
            "note": "Curated transfer task passed",
        },
    )
    assert r.status_code == 200
    vr = r.json()
    assert vr["gap"]["transfer_verified"] is True
    assert vr["gap"]["status"] == "recovered"

    r = client.get(f"/api/session/{sid}/map")
    assert r.status_code == 200

    r = client.get(f"/api/session/{sid}/privacy")
    assert r.status_code == 200

    r = client.post(f"/api/session/{sid}/close")
    assert r.status_code == 200


def test_complete_biology_loop():
    r = client.post("/api/session/start", json={"domain": "Biology"})
    assert r.status_code == 200
    sid = r.json()["session_id"]

    r = client.post(f"/api/session/{sid}/observe", json={
        "evidence": {
            "timestamp": "2026-08-17T13:00:00+05:30",
            "concept": "golgi",
            "secondary_concepts": ["rough_er"],
            "question_id": "scan_42",
            "selected_option": 1,
            "correct_option": 0,
            "distractor_pattern": "attributed_packaging_to_rer",
            "recurrence": True,
            "input_mode": "voice",
        }
    })
    assert r.status_code == 200

    r = client.get(f"/api/session/{sid}/diagnose")
    assert r.status_code == 200
    snap = r.json()

    q = snap.get("selected_question")
    if q:
        r = client.post(f"/api/session/{sid}/answer", json={
            "question_id": q["id"],
            "option_index": 1,
        })
        assert r.status_code == 200

    r = client.post(f"/api/session/{sid}/decide")
    assert r.status_code == 200

    r = client.get(f"/api/session/{sid}/retrieve", params={"target": "golgi", "query": "golgi packaging proteins"})
    assert r.status_code == 200

    r = client.post(f"/api/session/{sid}/teach", json={"target": "golgi"})
    assert r.status_code == 200

    r = client.post(
        f"/api/session/{sid}/mark-recovered",
        json={"passed": True, "note": "Biology original reassessment passed"},
    )
    assert r.status_code == 200
    assert r.json()["gap"]["status"] == "recovered_pending_transfer"

    selected = client.get(f"/api/session/{sid}/transfer-problem")
    assert selected.status_code == 200
    task_data = selected.json()
    assert task_data["available"] is True
    transfer_task = task_data["transfer_problem"]

    r = client.post(
        f"/api/session/{sid}/verify-transfer",
        json={
            "passed": True,
            "transfer_problem_id": transfer_task["id"],
            "original_problem_id": task_data["original_problem_id"],
            "structurally_different": task_data["structurally_different"],
            "note": "Curated Biology transfer task passed",
        },
    )
    assert r.status_code == 200
    assert r.json()["gap"]["status"] == "recovered"
    assert r.json()["gap"]["transfer_verified"] is True

    r = client.post(f"/api/session/{sid}/close")
    assert r.status_code == 200



def _install_pending_dsa_transfer(sid):
    data = session_manager.get_or_404(sid)
    session = data["session"]
    gap = LearningGap(
        gap_id=f"test-gap-{sid}",
        concept_id="binary_search",
        misconception_class="mc_boundary_update",
        hypothesis_probability=0.81,
        evidence_count=2,
        recurrence_count=1,
        status=GAP_RECOVERED_PENDING_TRANSFER,
        reassessment_result={"original_problem_id": "original-submission"},
        transfer_verified=False,
    )
    session.gap = gap
    data["pending_transfer_problem_id"] = "bs_practice_first_occurrence"
    data["pending_transfer_original_problem_id"] = "original-submission"
    session.asked_question_ids.add("bs_practice_first_occurrence")
    return data, gap


def test_valid_failed_transfer_reactivates_gap():
    started = client.post("/api/session/start", json={"domain": "DSA"})
    assert started.status_code == 200
    sid = started.json()["session_id"]
    _, gap = _install_pending_dsa_transfer(sid)

    result = client.post(
        f"/api/session/{sid}/verify-transfer",
        json={
            "passed": False,
            "transfer_problem_id": "bs_practice_first_occurrence",
            "original_problem_id": "original-submission",
            "structurally_different": True,
            "note": "Transfer attempt failed",
        },
    )

    assert result.status_code == 200
    assert result.json()["gap"]["status"] == "active_blocker"
    assert result.json()["gap"]["transfer_verified"] is False
    assert gap.status == "active_blocker"
    client.post(f"/api/session/{sid}/close")


def test_no_eligible_transfer_task_keeps_gap_pending(monkeypatch):
    started = client.post("/api/session/start", json={"domain": "DSA"})
    assert started.status_code == 200
    sid = started.json()["session_id"]
    _, gap = _install_pending_dsa_transfer(sid)
    monkeypatch.setitem(server_main.CURATED_TRANSFER_ITEMS, "binary_search", set())

    result = client.get(f"/api/session/{sid}/transfer-problem")

    assert result.status_code == 200
    body = result.json()
    assert body["available"] is False
    assert "No unused curated transfer task" in body["message"]
    assert body["gap"]["status"] == "recovered_pending_transfer"
    assert body["gap"]["transfer_verified"] is False
    assert gap.status == "recovered_pending_transfer"

    invalid = client.post(
        f"/api/session/{sid}/verify-transfer",
        json={
            "passed": True,
            "transfer_problem_id": "bs_practice_first_occurrence",
            "original_problem_id": "original-submission",
            "structurally_different": True,
        },
    )
    assert invalid.status_code == 409
    assert gap.status == "recovered_pending_transfer"
    assert gap.transfer_verified is False
    client.post(f"/api/session/{sid}/close")
