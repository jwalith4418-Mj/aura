"""Integration tests for the AURA API — complete learning loop coverage."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
    """Full DSA learning loop: start → observe → diagnose → answer → decide → retrieve → teach → verify → map → privacy → close."""
    # 1. Start session
    r = client.post("/api/session/start", json={"domain": "DSA"})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert r.json()["seeded_events"] == 2

    # 2. Check state after seeding
    r = client.get(f"/api/session/{sid}/state")
    assert r.status_code == 200
    concepts = r.json()["concepts"]
    assert "binary_search" in concepts

    # 3. Observe new evidence (recurring boundary bug)
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
    ev = r.json()
    assert ev["outcome"] == "failed"
    assert ev["concepts_state"]["binary_search"]["status"] in ("needs_review", "developing", "active_blocker")

    # 4. Diagnose
    r = client.get(f"/api/session/{sid}/diagnose")
    assert r.status_code == 200
    snap = r.json()
    assert "entropy" in snap
    assert "hypotheses" in snap
    assert len(snap["hypotheses"]) > 0
    # Entropy should be a positive number
    assert snap["entropy"] > 0

    # 5. Answer diagnostic question (if one was selected)
    q = snap.get("selected_question")
    if q:
        # Find the answer that maximally supports boundary_update
        q_id = q["id"]
        r = client.post(f"/api/session/{sid}/answer", json={
            "question_id": q_id,
            "option_index": 2,  # the while-loop option that indicates boundary confusion
        })
        assert r.status_code == 200
        snap2 = r.json()
        assert "hypotheses" in snap2

    # 6. Decide
    r = client.post(f"/api/session/{sid}/decide")
    assert r.status_code == 200
    outcome = r.json()
    assert outcome["decision"] in ("teach", "abstain")

    # 7. Retrieve grounded content
    r = client.get(f"/api/session/{sid}/retrieve", params={"target": "binary_search", "query": "boundary interval shrink"})
    assert r.status_code == 200
    ret = r.json()
    assert "chunks" in ret
    assert "citations" in ret

    # 8. Teach
    r = client.post(f"/api/session/{sid}/teach", json={"target": "binary_search"})
    assert r.status_code == 200
    teach = r.json()
    assert "message" in teach
    assert "action" in teach
    assert isinstance(teach["citations"], list)

    # 9. Check gap
    r = client.get(f"/api/session/{sid}/gap")
    assert r.status_code == 200

    # 10. Transfer cannot skip original reassessment or accept an arbitrary task.
    gap = r.json().get("gap")
    if gap:
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
        before = client.get(f"/api/session/{sid}/gap").json()["gap"]
        assert before["status"] == "intervention_applied"
        assert before["transfer_verified"] is False

        r = client.post(
            f"/api/session/{sid}/mark-recovered",
            json={"passed": True, "note": "Original problem reassessment passed"},
        )
        assert r.status_code == 200
        assert r.json()["gap"]["status"] == "recovered_pending_transfer"

        selected = client.get(f"/api/session/{sid}/transfer-problem")
        assert selected.status_code == 200
        task_data = selected.json()
        assert task_data["available"] is True
        transfer_task = task_data["transfer_problem"]

        # No structural confirmation and an arbitrary selection leave the gap pending.
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

    # 11. Learning map
    r = client.get(f"/api/session/{sid}/map")
    assert r.status_code == 200
    assert "map_text" in r.json()
    assert len(r.json()["map_text"]) > 0

    # 12. Privacy capsule
    r = client.get(f"/api/session/{sid}/privacy")
    assert r.status_code == 200
    priv = r.json()
    assert "capsule" in priv
    assert priv["capsule"]["dry_run"] is True
    assert "claim" in priv

    # 13. Close session
    r = client.post(f"/api/session/{sid}/close")
    assert r.status_code == 200


def test_complete_biology_loop():
    """Full Biology learning loop."""
    # 1. Start
    r = client.post("/api/session/start", json={"domain": "Biology"})
    assert r.status_code == 200
    sid = r.json()["session_id"]

    # 2. Observe MCQ evidence
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
    assert r.json()["outcome"] == "failed"

    # 3. Diagnose
    r = client.get(f"/api/session/{sid}/diagnose")
    assert r.status_code == 200
    snap = r.json()
    assert snap["entropy"] > 0

    # 4. Answer diagnostic
    q = snap.get("selected_question")
    if q:
        r = client.post(f"/api/session/{sid}/answer", json={
            "question_id": q["id"],
            "option_index": 1,  # Rough ER — indicates RER/Golgi confusion
        })
        assert r.status_code == 200

    # 5. Decide
    r = client.post(f"/api/session/{sid}/decide")
    assert r.status_code == 200

    # 6. Retrieve
    r = client.get(f"/api/session/{sid}/retrieve", params={"target": "golgi", "query": "golgi packaging proteins"})
    assert r.status_code == 200

    # 7. Teach
    r = client.post(f"/api/session/{sid}/teach", json={"target": "golgi"})
    assert r.status_code == 200
    assert "message" in r.json()

    # 8. Map
    r = client.get(f"/api/session/{sid}/map")
    assert r.status_code == 200

    # 9. Privacy
    r = client.get(f"/api/session/{sid}/privacy")
    assert r.status_code == 200
    assert r.json()["capsule"]["dry_run"] is True

    # 10. Close
    r = client.post(f"/api/session/{sid}/close")
    assert r.status_code == 200


def test_items_endpoint():
    r = client.post("/api/session/start", json={"domain": "DSA"})
    sid = r.json()["session_id"]

    r = client.get(f"/api/session/{sid}/items")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0
    assert all("prompt" in q for q in items)

    # Filter by kind
    r = client.get(f"/api/session/{sid}/items", params={"kind": "diagnostic"})
    assert r.status_code == 200
    diag_items = r.json()["items"]
    assert all(q["kind"] == "diagnostic" for q in diag_items)

    client.post(f"/api/session/{sid}/close")



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
