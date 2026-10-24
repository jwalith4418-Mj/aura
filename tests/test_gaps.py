import unittest

from adaptive.core.gaps import GapRegistry, make_transfer_check, select_transfer_problem
from adaptive.core.learner_state import LearnerStateEngine
from adaptive.domains import get_pack
from adaptive.types import (
    GAP_ACTIVE_BLOCKER,
    GAP_CANDIDATE,
    GAP_INTERVENTION_APPLIED,
    GAP_RECOVERED,
    GAP_RECOVERED_PENDING_TRANSFER,
    Event,
    GapHypothesis,
    Question,
    TransferCheck,
)


class TestGapLifecycle(unittest.TestCase):
    def setUp(self):
        self.pack = get_pack("DSA")
        self.registry = GapRegistry()
        self.state = LearnerStateEngine(self.pack.bkt_defaults)
        self.event = Event(
            event_id="evt-1", session_id="s1", timestamp="2026-08-17T22:00:00+05:30",
            subject="DSA", concepts=["binary_search"], activity="code_submission",
            input_mode="code", evaluation={"correct": False},
        )
        self.hyp = GapHypothesis(
            concept_id="mc_boundary_update", kind="misconception",
            prior=0.3, posterior=0.81, recurrence_count=2,
        )

    def test_materialize_creates_active_blocker(self):
        gap = self.registry.materialize("binary_search", self.hyp, self.event, self.pack.graph, self.state)
        self.assertEqual(gap.status, GAP_ACTIVE_BLOCKER)
        self.assertIn("arrays", gap.prerequisites_affected)
        self.assertEqual(gap.hypothesis_probability, 0.81)
        self.assertIn("evt-1", gap.evidence_ids)

    def test_gap_is_never_recovered_without_transfer(self):
        gap = self.registry.materialize("binary_search", self.hyp, self.event, self.pack.graph, self.state)
        self.registry.mark_intervention_applied(gap, "int-1")
        self.assertEqual(gap.status, GAP_INTERVENTION_APPLIED)
        self.registry.mark_original_recovered(gap, {"retry": "passed"})
        self.assertEqual(gap.status, GAP_RECOVERED_PENDING_TRANSFER)
        self.assertFalse(gap.transfer_verified)

    def test_transfer_success_recovers_gap(self):
        gap = self.registry.materialize("binary_search", self.hyp, self.event, self.pack.graph, self.state)
        self.registry.mark_intervention_applied(gap, "int-1")
        self.registry.mark_original_recovered(gap, {"retry": "passed"})
        transfer = select_transfer_problem(self.pack.items, "binary_search")
        self.assertIsNotNone(transfer)
        check = make_transfer_check(transfer, None, passed=True, structurally_different=True)
        self.registry.verify_transfer(gap, check)
        self.assertEqual(gap.status, GAP_RECOVERED)
        self.assertTrue(gap.transfer_verified)

    def test_transfer_failure_reactivates_gap(self):
        gap = self.registry.materialize("binary_search", self.hyp, self.event, self.pack.graph, self.state)
        self.registry.mark_intervention_applied(gap, "int-1")
        self.registry.mark_original_recovered(gap, {"retry": "passed"})
        transfer = select_transfer_problem(self.pack.items, "binary_search")
        check = make_transfer_check(transfer, None, passed=False, structurally_different=True)
        self.registry.verify_transfer(gap, check)
        self.assertEqual(gap.status, GAP_ACTIVE_BLOCKER)
        self.assertFalse(gap.transfer_verified)

    def test_transfer_cannot_skip_original_reassessment(self):
        gap = self.registry.materialize("binary_search", self.hyp, self.event, self.pack.graph, self.state)
        transfer = select_transfer_problem(self.pack.items, "binary_search")
        check = make_transfer_check(transfer, None, passed=True, structurally_different=True)

        self.registry.verify_transfer(gap, check)

        self.assertEqual(gap.status, GAP_ACTIVE_BLOCKER)
        self.assertFalse(gap.transfer_verified)

    def test_wrong_concept_transfer_cannot_verify_recovery(self):
        gap = self.registry.materialize("binary_search", self.hyp, self.event, self.pack.graph, self.state)
        self.registry.mark_intervention_applied(gap, "int-1")
        self.registry.mark_original_recovered(gap, {"retry": "passed"})
        check = TransferCheck(
            transfer_problem_id="biology-item",
            concept_id="cell_organelles",
            original_problem_id="original-item",
            prompt="Different domain",
            structurally_different=True,
            passed=True,
        )

        self.registry.verify_transfer(gap, check)

        self.assertEqual(gap.status, GAP_RECOVERED_PENDING_TRANSFER)
        self.assertFalse(gap.transfer_verified)

    def test_transfer_check_does_not_infer_structure_from_a_different_id(self):
        transfer = select_transfer_problem(self.pack.items, "binary_search")
        check = make_transfer_check(transfer, None, passed=True)

        self.assertFalse(check.structurally_different)

        gap = self.registry.materialize("binary_search", self.hyp, self.event, self.pack.graph, self.state)
        self.registry.mark_intervention_applied(gap, "int-1")
        self.registry.mark_original_recovered(gap, {"retry": "passed"})
        self.registry.verify_transfer(gap, check)

        self.assertEqual(gap.status, GAP_RECOVERED_PENDING_TRANSFER)
        self.assertFalse(gap.transfer_verified)

    def test_same_problem_cannot_count_as_transfer(self):
        gap = self.registry.materialize("binary_search", self.hyp, self.event, self.pack.graph, self.state)
        self.registry.mark_intervention_applied(gap, "int-1")
        self.registry.mark_original_recovered(gap, {"retry": "passed"})
        transfer = select_transfer_problem(self.pack.items, "binary_search")
        check = make_transfer_check(transfer, transfer.id, passed=True, structurally_different=True)

        self.registry.verify_transfer(gap, check)

        self.assertEqual(gap.status, GAP_RECOVERED_PENDING_TRANSFER)
        self.assertFalse(gap.transfer_verified)

    def test_transfer_selection_never_falls_back_to_an_unrelated_concept(self):
        unrelated = Question(
            id="biology-item",
            concept_id="cell_organelles",
            kind="practice",
            prompt="An unrelated question",
            options=["A", "B"],
        )

        self.assertIsNone(
            select_transfer_problem(
                [unrelated],
                concept_id="binary_search",
                original_problem_id="original-item",
            )
        )

    def test_low_confidence_materializes_as_candidate(self):
        low = GapHypothesis("mc_off_by_one", "misconception", 0.2, 0.4, recurrence_count=0)
        gap = self.registry.materialize("binary_search", low, self.event, self.pack.graph, self.state)
        self.assertEqual(gap.status, GAP_CANDIDATE)


if __name__ == "__main__":
    unittest.main()