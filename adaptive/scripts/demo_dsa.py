from __future__ import annotations

"""AURA killer demo (section 11) - DSA diagnostic + transfer-verified recovery loop.

Run:  python -m adaptive.scripts.demo_dsa
"""

import json

from adaptive.privacy.capsule import PRIVACY_CLAIM
from adaptive.core.gaps import make_transfer_check, select_transfer_problem
from adaptive.core.graph_projection import render_learning_map
from adaptive.core.session import AdaptiveSession
from adaptive.domains import get_pack
from adaptive.types import ConceptState, GAP_RECOVERED, STATUS_VERIFIED

SEED_CODE = "while low < high:\n    mid = (low + high) // 2\n    if arr[mid] < target:\n        low = mid\n    else:\n        high = mid"
FIXED_CODE = "while low < high:\n    mid = (low + high) // 2\n    if arr[mid] < target:\n        low = mid + 1\n    else:\n        high = mid"
TRANSFER_CODE = (
    "def first_occurrence(arr, target):\n"
    "    lo, hi = 0, len(arr)\n"
    "    while lo < hi:\n"
    "        mid = (lo + hi) // 2\n"
    "        if arr[mid] < target:\n"
    "            lo = mid + 1\n"
    "        else:\n"
    "            hi = mid\n"
    "    return lo if lo < len(arr) and arr[lo] == target else -1"
)


def check_first_occurrence(code: str, cases) -> tuple[bool, str]:
    ns: dict = {}
    sandbox_builtins = {"len": len, "range": range, "min": min, "max": max, "abs": abs, "int": int}
    try:
        exec(code, {"__builtins__": sandbox_builtins}, ns)  # demo-only: real product uses the sandbox service
        fn = ns.get("first_occurrence")
        if not callable(fn):
            return False, "function first_occurrence not defined"
        for arr, target, expected in cases:
            got = fn(arr, target)
            if got != expected:
                return False, f"case arr={arr} target={target}: got {got}, expected {expected}"
        return True, "all transfer test cases passed"
    except Exception as e:  # noqa: BLE001
        return False, f"error: {e}"


def seed_history(session: AdaptiveSession) -> None:
    session.start_session("DSA-20260810-S01")
    for i, (day, hour) in enumerate(((10, 19), (12, 18))):
        session.observe(
            {
                "session_id": session.current_session_id,
                "timestamp": f"2026-08-{day:02d}T{hour:02d}:10:00+05:30",
                "concept": "binary_search",
                "secondary_concepts": ["boundary_handling"],
                "test_results": {"passed": ["normal_asc", "normal_desc"], "failed": ["left_boundary"] if i == 1 else ["left_boundary", "duplicate_values"]},
                "failure_classes": ["left_boundary", "duplicate_values"] if i == 1 else ["left_boundary"],
                "static_pattern": "low_mid_no_increment",
                "recurrence": True,
                "code": SEED_CODE,
            }
        )


def _posterior_bars(snapshot) -> str:
    ranked = snapshot.ranked()[:5]
    width = 24
    lines = []
    for h in ranked:
        filled = int(h.posterior * width)
        lines.append(f"    {h.concept_id:<30} {'#' * filled:<{width}} {h.posterior:.2f}")
    return "\n".join(lines)


def main() -> None:
    pack = get_pack("DSA")
    session = AdaptiveSession(pack)
    seed_history(session)

    print("=" * 76)
    print("AURA  -  Active Gap Diagnosis Engine  (PS17 / PS10)")
    print("DSA killer demo: diagnose -> ask -> teach -> transfer-verify -> update")
    print("=" * 76)

    print("\n[1] LEARNING MAP (seeded history: recurring boundary failures)\n")
    print(render_learning_map(pack.graph, session.state, "DSA"))

    print("\n[2] LEARNER SUBMITS BINARY SEARCH\n")
    print("    ```python")
    print("\n".join("    " + l for l in SEED_CODE.splitlines()))
    print("    ```")
    session.observe(
        {
            "timestamp": "2026-08-17T22:10:00+05:30",
            "concept": "binary_search",
            "secondary_concepts": ["boundary_handling"],
            "test_results": {"passed": ["normal_asc", "normal_desc"], "failed": ["left_boundary", "single_element"]},
            "failure_classes": ["left_boundary", "single_element"],
            "static_pattern": "low_mid_no_increment",
            "recurrence": True,
            "code": SEED_CODE,
        }
    )
    print("\n    VERDICT: normal cases PASS   |   boundary cases FAIL (left_boundary, single_element)")
    print("    pattern detected: low = mid without strict progress   |   historical recurrence: yes")
    st = session.state.state("binary_search")
    print(f"    BKT belief for binary_search after evidence: {st.mastery_belief:.2f} ({st.current_status})")

    print("\n[3] AURA DOES NOT EXPLAIN YET - it shows the hypothesis distribution (live)\n")
    snap = session.diagnose()
    print("    blocking-gap hypotheses (P(g | evidence, curriculum)):\n")
    print(_posterior_bars(snap))
    print(f"    entropy H = {snap.entropy:.2f}  (uncertain -> ask, do not guess)")

    print("\n[4] AURA ASKS THE ONE QUESTION THAT MAXIMISES INFORMATION GAIN\n")
    q = session.engine.select_question(snap.hyps, pack.questions("diagnostic"))
    print(f"    QUESTION (IG-maximising, cost {q.cost}):")
    print(f"      {q.prompt}")
    for i, opt in enumerate(q.options):
        print(f"        {chr(65 + i)}) {opt}")

    signature = max(range(len(q.options)), key=lambda i: q.likelihood["mc_boundary_update"][i])
    print(f"\n    LEARNER ANSWERS: {chr(65 + signature)}) {q.options[signature]}")

    print("\n[5] POSTERIOR UPDATES LIVE ON SCREEN\n")
    snap2 = session.answer_diagnostic(q, signature)
    print(_posterior_bars(snap2))
    print(f"    entropy H = {snap2.entropy:.2f}  ->  confidence on boundary-update gap now clear")

    print("\n[6] GAP PANEL\n")
    outcome = session.decide(snap2)
    print(f"    LIKELY BLOCKING GAP (hypothesis, not 'root cause')")
    print(f"      concept:          binary_search.boundary_handling")
    print(f"      current hyp:      {outcome.gap.misconception_class if outcome.gap else 'boundary_update'}")
    print(f"      probability:      {snap2.top().posterior:.2f}")
    print(f"      evidence:         2 boundary test failures + static pattern + 2 prior recurrences")
    print(f"      status:           {outcome.gap.status if outcome.gap else 'candidate'}")
    print(f"      next:             one targeted hint before continuing - NOT the full solution")

    print("\n[7] LOCAL TUTOR GIVES A HINT (not the fix)\n")
    bundle = session.retrieve("binary_search", "boundary interval shrink progress", k=2)
    response = session.teach(outcome, "binary_search", bundle)
    print(f"    AURA ({response.action}):")
    print(f"      {response.message}")
    if response.citations:
        print(f"    grounded in: {response.citations}")
    if response.next_check:
        print(f"    next check:  {response.next_check}")
    gap = session.current_gap()
    print(f"    gap status: {gap.status}   intervention recorded: {session.last_intervention_id}")

    print("\n[8] LEARNER CORRECTS THE IMPLEMENTATION (original tests now pass)\n")
    session.observe(
        {
            "timestamp": "2026-08-17T22:12:01+05:30",
            "concept": "binary_search",
            "secondary_concepts": ["boundary_handling"],
            "test_results": {"passed": ["normal_asc", "normal_desc", "left_boundary", "single_element", "duplicate_values"], "failed": []},
            "failure_classes": [],
            "static_pattern": None,
            "recurrence": False,
            "intervention_id": session.last_intervention_id,
            "code": FIXED_CODE,
        }
    )
    session.gaps.mark_original_recovered(gap, {"retry": "passed", "test_failures": 0})
    print(f"    VERDICT: all tests PASS  ->  gap status: {gap.status}")
    print("    AURA does NOT mark this recovered. Passing corrected code can be trial-and-error.")

    print("\n[9] TRANSFER VERIFICATION - structurally different problem, same concept\n")
    transfer_item = select_transfer_problem(pack.items, "binary_search")
    if transfer_item is None:
        print("    No same-concept transfer problem is available; recovery remains unverified.")
        return
    print(f"    TRANSFER PROBLEM ({transfer_item.id}):")
    print(f"      {transfer_item.prompt}")
    print("    ```python")
    print("\n".join("    " + l for l in TRANSFER_CODE.splitlines()))
    print("    ```")
    passed, note = check_first_occurrence(
        TRANSFER_CODE,
        [([1, 1, 2, 2, 3], 2, 2), ([5], 5, 0), ([1, 2, 3], 4, -1), ([2, 2, 2, 2], 2, 0)],
    )
    # This demo explicitly selects the first-occurrence variant as a structurally
    # different transfer task; the helper does not infer that from the ID alone.
    check = make_transfer_check(
        transfer_item,
        original_problem_id=None,
        passed=passed,
        note=note,
        structurally_different=True,
    )
    session.gaps.verify_transfer(gap, check)

    print(f"    transfer evaluation: {note}")
    print(f"    VERDICT: {check.prompt[:40]}...  ->  transfer_verified = {gap.transfer_verified}")
    print(f"    gap status: {gap.status}   recovery confidence: {gap.recovery_confidence:.2f}")

    print("\n[10] LEARNING MAP AFTER RECOVERY\n")
    session.state.set_state(
        ConceptState(
            concept_id="boundary_handling",
            mastery_belief=0.82,
            state_confidence="medium",
            evidence_count=9,
            last_observed_at="2026-08-17T22:14:00+05:30",
            current_status=STATUS_VERIFIED,
            recurrence_count=2,
            active_gap_state=None,
            recovery_state="recovered",
        )
    )
    print(render_learning_map(pack.graph, session.state, "DSA"))
    print(f"    gap lifecycle: active_blocker -> recovered_pending_transfer -> recovered (transfer_verified=True)")
    assert gap.status == GAP_RECOVERED and gap.transfer_verified

    print("\n[11] PRIVACY INSPECTOR - what WOULD be sent, nothing was\n")
    capsule = session.privacy_capsule(bundle=bundle)
    print("    \"" + PRIVACY_CLAIM + "\"")
    print("\n    capsule (dry_run=true - no remote call exists in this engine):")
    for line in json.dumps(capsule, indent=2).splitlines():
        print("      " + line)
    print("\n    Remote (if ever gated) = only this capsule; everything else stays local.")

    print("\n    The loop: OBSERVE -> STATE -> DIAGNOSE -> ASK -> TEACH -> VERIFY -> UPDATE")


if __name__ == "__main__":
    main()