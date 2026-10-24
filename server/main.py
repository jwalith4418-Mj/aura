"""AURA — FastAPI backend wrapping the adaptive learning engine.

Every endpoint maps to an existing AdaptiveSession method with fail-safe fallbacks.
The engine code (adaptive/) is never modified.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.schemas import (
    StartSessionRequest,
    ObserveRequest,
    AnswerDiagnosticRequest,
    MarkRecoveredRequest,
    TransferVerifyRequest,
    TeachRequest,
)
from server.session_manager import session_manager

from adaptive.domains import get_pack, available_packs
from adaptive.core.session import AdaptiveSession
from adaptive.core.gaps import select_transfer_problem, make_transfer_check
from adaptive.core.graph_projection import render_learning_map
from adaptive.types import GAP_INTERVENTION_APPLIED, GAP_RECOVERED_PENDING_TRANSFER

app = FastAPI(title="AURA — Adaptive Learning Diagnosis Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_question(q):
    if q is None:
        return None
    return {
        "id": q.id,
        "concept_id": q.concept_id,
        "kind": q.kind,
        "prompt": q.prompt,
        "options": list(q.options),
        "correct_index": q.correct_index,
        "cost": q.cost,
        "distractors": dict(q.distractors) if q.distractors else {},
    }


def _why_asking_rationale(snap) -> str:
    if not snap.selected_question:
        return "No further diagnostic question needed — posterior confidence clears threshold."
    q = snap.selected_question
    top_hyp = snap.top().concept_id if snap.hyps else "unknown"
    return f"AURA selected '{q.id}' (Information Gain maximised) to disambiguate candidate '{top_hyp}' from competing misconception hypotheses."


# These IDs are curated as structurally different transfer tasks for their
# corresponding concept. Being a practice item or having a different ID alone
# is not sufficient to prove transfer difference.
CURATED_TRANSFER_ITEMS = {
    "binary_search": {"bs_practice_first_occurrence"},
    "boundary_handling": {"bs_practice_upper_bound"},
    "golgi": {"bio_reassess_golgi"},
    "protein_processing": {"bio_practice_secretion"},
    "lysosome": {"bio_practice_lysosome"},
}


def _serialize_snapshot(snap):
    live = snap.as_live()
    return {
        "target": live["target"],
        "insufficient": live["insufficient"],
        "entropy": round(live["entropy"], 4),
        "hypotheses": live["hypotheses"],
        "selected_question_id": live.get("selected_question_id"),
        "selected_question": _serialize_question(snap.selected_question),
        "why_asking": _why_asking_rationale(snap),
    }


def _serialize_gap(gap):
    if gap is None:
        return None
    return {
        "gap_id": gap.gap_id,
        "concept_id": gap.concept_id,
        "misconception_class": gap.misconception_class,
        "hypothesis_probability": round(gap.hypothesis_probability, 4),
        "evidence_count": gap.evidence_count,
        "recurrence_count": gap.recurrence_count,
        "prerequisites_affected": list(gap.prerequisites_affected),
        "evidence_ids": list(gap.evidence_ids),
        "first_detected": gap.first_detected,
        "last_confirmed": gap.last_confirmed,
        "status": gap.status,
        "intervention_ids": list(gap.intervention_ids),
        "transfer_verified": gap.transfer_verified,
        "recovery_confidence": round(gap.recovery_confidence, 4),
    }


def _serialize_event(event):
    return {
        "event_id": event.event_id,
        "session_id": event.session_id,
        "timestamp": event.timestamp,
        "subject": event.subject,
        "concepts": list(event.concepts),
        "activity": event.activity,
        "input_mode": event.input_mode,
        "evaluation": dict(event.evaluation) if event.evaluation else {},
        "outcome": event.outcome,
    }


def _serialize_chunk(chunk):
    return {
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "topic": chunk.topic,
        "text": chunk.text,
        "concept_ids": list(chunk.concept_ids),
        "difficulty_band": chunk.difficulty_band,
    }


def _seed_history(session: AdaptiveSession, domain: str) -> list:
    seeded = []
    if domain == "DSA":
        for i, (day, hour) in enumerate(((10, 19), (12, 18))):
            ev = session.observe({
                "session_id": session.current_session_id,
                "timestamp": f"2026-08-{day:02d}T{hour:02d}:10:00+05:30",
                "concept": "binary_search",
                "secondary_concepts": ["boundary_handling"],
                "test_results": {
                    "passed": ["normal_asc", "normal_desc"],
                    "failed": ["left_boundary"] if i == 1 else ["left_boundary", "duplicate_values"],
                },
                "failure_classes": ["left_boundary", "duplicate_values"] if i == 1 else ["left_boundary"],
                "static_pattern": "low_mid_no_increment",
                "recurrence": True,
                "code": "while low < high:\n    mid = (low + high) // 2\n    if arr[mid] < target:\n        low = mid\n    else:\n        high = mid",
            })
            seeded.append(ev.event_id)
    elif domain == "Biology":
        for i, (day, hour) in enumerate(((11, 12), (13, 12))):
            ev = session.observe({
                "session_id": session.current_session_id,
                "timestamp": f"2026-08-{day:02d}T{hour:02d}:00:00+05:30",
                "concept": "golgi",
                "secondary_concepts": ["rough_er"],
                "question_id": f"q{i}",
                "selected_option": 1,
                "correct_option": 0,
                "distractor_pattern": "attributed_packaging_to_rer",
                "recurrence": True,
                "input_mode": "voice",
            })
            seeded.append(ev.event_id)
    return seeded


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "AURA", "version": "0.1.0"}


@app.get("/api/domains")
def domains():
    packs = available_packs()
    info = []
    for name in packs:
        pack = get_pack(name)
        info.append({
            "name": name,
            "subject": pack.subject,
            "description": f"{pack.subject} domain pack ({len(pack.items)} items, {len(pack.corpus)} chunks)",
            "concepts": [n.name for n in pack.graph.nodes.values() if n.kind == "concept"],
        })
    return {"domains": info}


@app.post("/api/session/start")
def start_session(req: StartSessionRequest):
    if req.domain not in available_packs():
        raise HTTPException(status_code=400, detail=f"Invalid domain: {req.domain!r}. Available: {available_packs()}")

    pack = get_pack(req.domain)
    session = AdaptiveSession(pack=pack)
    session_key = f"{req.domain}-{_iso_now()}"
    session_id = session.start_session(session_key=session_key)

    seeded = _seed_history(session, req.domain)

    session_manager.create(session_id, {
        "session": session,
        "pack": pack,
        "domain": req.domain,
        "last_snap": None,
        "last_outcome": None,
        "last_bundle": None,
    })

    return {
        "session_id": session_id,
        "domain": req.domain,
        "seeded_events": len(seeded),
    }


@app.get("/api/session/{sid}/state")
def get_state(sid: str):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]
    return {"concepts": session.state.to_dict()}


@app.post("/api/session/{sid}/observe")
def observe(sid: str, req: ObserveRequest):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]

    raw = dict(req.evidence)
    if "session_id" not in raw:
        raw["session_id"] = session.current_session_id
    if "timestamp" not in raw:
        raw["timestamp"] = _iso_now()

    event = session.observe(raw)

    concepts_state = {}
    for cid in event.concepts:
        st = session.state.state(cid)
        concepts_state[cid] = {
            "mastery_belief": round(st.mastery_belief, 4),
            "status": st.current_status,
            "evidence_count": st.evidence_count,
        }

    return {
        **_serialize_event(event),
        "concepts_state": concepts_state,
    }


@app.get("/api/session/{sid}/diagnose")
def diagnose(sid: str, target: str = Query(default=None)):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]

    snap = session.diagnose(target=target, randomize_ties=True)
    session_manager.update(sid, {"last_snap": snap})

    return _serialize_snapshot(snap)


@app.post("/api/session/{sid}/next-question")
def next_question(sid: str):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]

    last_snap = data.get("last_snap")
    if last_snap and last_snap.selected_question:
        session.asked_question_ids.add(last_snap.selected_question.id)

    snap = session.diagnose()
    session_manager.update(sid, {"last_snap": snap})

    return _serialize_snapshot(snap)


@app.post("/api/session/{sid}/answer")
def answer_diagnostic(sid: str, req: AnswerDiagnosticRequest):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]
    pack = data["pack"]

    question = next((q for q in pack.items if q.id == req.question_id), None)
    if question is None:
        raise HTTPException(status_code=400, detail=f"Question not found: {req.question_id}")
    if req.option_index < 0 or req.option_index >= len(question.options):
        raise HTTPException(status_code=400, detail=f"Invalid option_index: {req.option_index}")

    old_snap = data.get("last_snap")
    old_entropy = old_snap.entropy if old_snap else 0.0

    snap = session.answer_diagnostic(question, req.option_index)
    session_manager.update(sid, {"last_snap": snap})

    serialized = _serialize_snapshot(snap)
    serialized["what_changed"] = {
        "entropy_before": round(old_entropy, 4),
        "entropy_after": round(snap.entropy, 4),
        "entropy_delta": round(old_entropy - snap.entropy, 4),
        "leading_hypothesis": snap.top().concept_id if snap.hyps else None,
        "leading_probability": round(snap.top().posterior, 4) if snap.hyps else 0.0,
    }
    return serialized


@app.post("/api/session/{sid}/decide")
def decide(sid: str):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]
    snap = data.get("last_snap")

    if snap is None and session.active_event:
        snap = session.diagnose()
        session_manager.update(sid, {"last_snap": snap})

    outcome = session.decide(snapshot=snap)

    if outcome.gap is None and getattr(session, "active_hyps", None):
        target = session.active_event.concepts[0] if session.active_event else session.pack.items[0].concept_id
        top = session.engine.top_hypothesis(session.active_hyps)
        gap = session.gaps.materialize(target, top, session.active_event, session.pack.graph, session.state)
        session.gap = gap
        outcome.gap = gap

    session_manager.update(sid, {"last_outcome": outcome})

    return {
        "decision": outcome.decision,
        "action": outcome.action,
        "reason": outcome.reason,
        "insufficiency_cause": outcome.insufficiency_cause,
        "gap": _serialize_gap(outcome.gap),
    }


@app.get("/api/session/{sid}/retrieve")
def retrieve(sid: str, target: str, query: str, k: int = Query(default=3)):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]

    bundle = session.retrieve(target, query, k)
    session_manager.update(sid, {"last_bundle": bundle})

    return {
        "chunks": [_serialize_chunk(c) for c in bundle.chunks],
        "citations": list(bundle.citations),
        "retrieval_latency_ms": round(bundle.retrieval_latency_ms, 2),
    }


@app.post("/api/session/{sid}/teach")
def teach(sid: str, req: TeachRequest):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]
    pack = data["pack"]
    outcome = data.get("last_outcome")
    bundle = data.get("last_bundle")

    if outcome is None:
        outcome = session.decide()
        session_manager.update(sid, {"last_outcome": outcome})

    if bundle is None:
        target = req.target or (session.active_event.concepts[0] if session.active_event else pack.items[0].concept_id)
        bundle = session.retrieve(target, "boundary progress shrink", k=3)
        session_manager.update(sid, {"last_bundle": bundle})

    response = session.teach(outcome, req.target, bundle)

    return {
        "action": response.action,
        "message": response.message,
        "next_check": response.next_check,
        "citations": list(response.citations),
        "meta": dict(response.meta) if response.meta else {},
        "gap_status": session.current_gap().status if session.current_gap() else None,
        "intervention_id": session.last_intervention_id,
    }


@app.post("/api/session/{sid}/mark-recovered")
def mark_recovered(sid: str, req: MarkRecoveredRequest):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]
    gap = session.current_gap()

    if gap is None:
        raise HTTPException(status_code=409, detail="No diagnosed learning gap exists; original reassessment cannot be recorded.")

    if gap.status != GAP_INTERVENTION_APPLIED:
        raise HTTPException(
            status_code=409,
            detail=f"Original reassessment requires status {GAP_INTERVENTION_APPLIED!r}; current status is {gap.status!r}.",
        )

    original_problem_id = req.original_problem_id or (
        session.active_event.event_id if session.active_event else None
    )
    if not original_problem_id:
        raise HTTPException(status_code=409, detail="No original problem/evidence ID is available for reassessment.")

    if not req.passed:
        return {
            "gap": _serialize_gap(gap),
            "recovered": False,
            "message": "Original reassessment did not pass. Transfer verification is unavailable until the original problem passes.",
        }

    session.gaps.mark_original_recovered(
        gap,
        {
            "retry": "passed",
            "note": req.note,
            "original_problem_id": original_problem_id,
        },
    )
    data["pending_transfer_problem_id"] = None
    data["pending_transfer_original_problem_id"] = original_problem_id

    return {
        "gap": _serialize_gap(gap),
        "recovered": False,
        "message": "Original reassessment passed. Gap remains recovered_pending_transfer until a curated transfer task passes.",
    }


@app.get("/api/session/{sid}/transfer-problem")
def get_transfer_problem(sid: str):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]
    pack = data["pack"]
    gap = session.current_gap()

    if gap is None:
        raise HTTPException(status_code=409, detail="No diagnosed learning gap exists; no transfer task can be selected.")
    if gap.status != GAP_RECOVERED_PENDING_TRANSFER:
        raise HTTPException(
            status_code=409,
            detail=f"Transfer task requires status {GAP_RECOVERED_PENDING_TRANSFER!r}; current status is {gap.status!r}.",
        )

    original_problem_id = (gap.reassessment_result or {}).get("original_problem_id")
    if not original_problem_id:
        raise HTTPException(status_code=409, detail="Original reassessment must identify the source problem before selecting transfer.")

    curated_ids = CURATED_TRANSFER_ITEMS.get(gap.concept_id, set())
    curated_items = [q for q in pack.items if q.id in curated_ids]
    transfer_item = select_transfer_problem(
        curated_items,
        gap.concept_id,
        original_problem_id=original_problem_id,
        exclude_ids=session.asked_question_ids,
    )

    if transfer_item is None:
        data["pending_transfer_problem_id"] = None
        data["pending_transfer_original_problem_id"] = original_problem_id
        return {
            "available": False,
            "message": f"No unused curated transfer task is available for concept {gap.concept_id!r}. Recovery remains unverified.",
            "gap": _serialize_gap(gap),
            "original_problem_id": original_problem_id,
        }

    # Persist the offered task so the verify endpoint cannot accept an arbitrary
    # or stale item ID. This task is also excluded from subsequent selections.
    session.asked_question_ids.add(transfer_item.id)
    data["pending_transfer_problem_id"] = transfer_item.id
    data["pending_transfer_original_problem_id"] = original_problem_id
    return {
        "available": True,
        "message": "Curated same-concept transfer task selected; solve this structurally different task before recovery can be verified.",
        "gap": _serialize_gap(gap),
        "transfer_problem": _serialize_question(transfer_item),
        "original_problem_id": original_problem_id,
        "structurally_different": True,
    }


@app.post("/api/session/{sid}/verify-transfer")
def verify_transfer(sid: str, req: TransferVerifyRequest):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]
    pack = data["pack"]
    gap = session.current_gap()

    if gap is None:
        raise HTTPException(status_code=409, detail="No diagnosed learning gap exists; transfer cannot create one.")

    if gap.status != GAP_RECOVERED_PENDING_TRANSFER:
        raise HTTPException(
            status_code=409,
            detail=f"Transfer verification requires {GAP_RECOVERED_PENDING_TRANSFER!r}; current status is {gap.status!r}. Complete intervention and original reassessment first.",
        )

    expected_problem_id = data.get("pending_transfer_problem_id")
    expected_original_id = data.get("pending_transfer_original_problem_id")
    if not expected_problem_id or not expected_original_id:
        raise HTTPException(status_code=409, detail="No eligible transfer task is pending. Request /transfer-problem first.")

    if req.transfer_problem_id != expected_problem_id:
        raise HTTPException(status_code=400, detail="Transfer task ID does not match the task selected for this session.")
    if req.original_problem_id != expected_original_id:
        raise HTTPException(status_code=400, detail="Original problem ID does not match the recorded reassessment.")
    if not req.structurally_different:
        raise HTTPException(status_code=400, detail="Structural-difference confirmation is required for transfer verification.")

    transfer_item = next((q for q in pack.items if q.id == req.transfer_problem_id), None)
    curated_ids = CURATED_TRANSFER_ITEMS.get(gap.concept_id, set())
    if (
        transfer_item is None
        or transfer_item.id not in curated_ids
        or transfer_item.concept_id != gap.concept_id
        or transfer_item.kind not in ("practice", "reassessment")
        or transfer_item.id == expected_original_id
    ):
        raise HTTPException(status_code=400, detail="Selected task is not a valid curated transfer task for this gap.")

    confirmed_structural_difference = (
        req.structurally_different
        and transfer_item.id in curated_ids
        and transfer_item.concept_id == gap.concept_id
        and transfer_item.id != expected_original_id
    )
    if not confirmed_structural_difference:
        raise HTTPException(status_code=400, detail="The selected task lacks confirmed structural difference.")

    check = make_transfer_check(
        transfer_item,
        original_problem_id=expected_original_id,
        passed=req.passed,
        note=req.note,
        structurally_different=confirmed_structural_difference,
    )
    session.gaps.verify_transfer(gap, check)
    data["pending_transfer_problem_id"] = None

    return {
        "gap": _serialize_gap(gap),
        "transfer_problem": _serialize_question(transfer_item),
        "transfer_check": {
            "transfer_problem_id": check.transfer_problem_id,
            "passed": check.passed,
            "structurally_different": check.structurally_different,
            "evaluation_note": check.evaluation_note,
        },
        "message": (
            "Transfer verified; learning gap recovered."
            if gap.status == "recovered" and gap.transfer_verified
            else "Transfer did not pass. The learning gap is active again."
        ),
    }


@app.get("/api/session/{sid}/map")
def get_map(sid: str):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]
    pack = data["pack"]

    map_text = render_learning_map(pack.graph, session.state, pack.subject)
    return {"map_text": map_text, "subject": pack.subject}


@app.get("/api/session/{sid}/privacy")
def get_privacy(sid: str):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]
    bundle = data.get("last_bundle")

    capsule = session.privacy_capsule(bundle=bundle)

    from adaptive.privacy.capsule import PRIVACY_CLAIM
    return {
        "claim": PRIVACY_CLAIM,
        "capsule": capsule,
    }


@app.post("/api/session/{sid}/close")
def close_session(sid: str):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]

    summary = session.close_session()
    session_manager.remove(sid)

    return summary


@app.get("/api/session/{sid}/gap")
def get_gap(sid: str):
    data = session_manager.get_or_404(sid)
    session: AdaptiveSession = data["session"]

    gap = session.current_gap()
    if gap is None and session.gaps.gaps:
        gap = list(session.gaps.gaps.values())[-1]
    return {"gap": _serialize_gap(gap)}


@app.get("/api/session/{sid}/items")
def get_items(sid: str, kind: str = Query(default=None)):
    data = session_manager.get_or_404(sid)
    pack = data["pack"]

    items = pack.questions(kind) if kind else pack.items
    return {"items": [_serialize_question(q) for q in items]}


_frontend_dist = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend", "dist",
)
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
