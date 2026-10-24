import unittest

from adaptive.core.session import AdaptiveSession
from adaptive.domains import get_pack
from adaptive.types import (
    GAP_INTERVENTION_APPLIED,
    GAP_RECOVERED,
    GAP_RECOVERED_PENDING_TRANSFER,
)


class TestAdaptiveSession(unittest.TestCase):
    def setUp(self):
        self.pack = get_pack("DSA")
        self.session = AdaptiveSession(self.pack)
        self.session.start_session("TESTS-01")

    def _failed_submission(self, failure_classes, pattern, recurrence=True):
        return {
            "session_id": "TESTS-01",
            "timestamp": "2026-08-17T22:00:00+05:30",
            "event_id": "evt-tests-01",
            "concept": "binary_search",
            "secondary_concepts": ["boundary_handling"],
            "test_results": {"passed": ["normal"], "failed": failure_classes},
            "failure_classes": failure_classes,
            "static_pattern": pattern,
            "recurrence": recurrence,
            "code": "while low < high: low = mid",
        }

    def test_full_diagnose_answer_teach_flow(self):
        event = self.session.observe(self._failed_submission(["left_boundary", "single_element"], "low_mid_no_increment", True))
        snapshot = self.session.diagnose()
        self.assertEqual(snapshot.top().concept_id, "mc_boundary_update")
        self.assertGreater(snapshot.top().posterior, 0.5)

        question = snapshot.selected_question or self.session.engine.select_question(
            snapshot.hyps, self.pack.questions("diagnostic")
        )
        best = max(range(len(question.options)), key=lambda i: question.likelihood["mc_boundary_update"][i])
        snapshot = self.session.answer_diagnostic(question, best)
        self.assertGreater(snapshot.top().posterior, 0.6)

        outcome = self.session.decide(snapshot)
        self.assertEqual(outcome.decision, "teach")
        self.assertTrue(outcome.action)
        bundle = self.session.retrieve("binary_search", "strict interval shrink mid plus one", k=2)
        response = self.session.teach(outcome, "binary_search", bundle=bundle, question=question)
        self.assertTrue(response.message)
        self.assertTrue(response.citations)

        gap = self.session.current_gap()
        self.assertIsNotNone(gap)
        self.assertEqual(gap.status, GAP_INTERVENTION_APPLIED)

    def test_recovery_requires_transfer_verification(self):
        event = self.session.observe(self._failed_submission(["left_boundary", "single_element"], "low_mid_no_increment", True))
        question = self.session.engine.select_question(self.session.diagnose().hyps, self.pack.questions("diagnostic"))
        best = max(range(len(question.options)), key=lambda i: question.likelihood["mc_boundary_update"][i])
        snapshot = self.session.answer_diagnostic(question, best)
        outcome = self.session.decide(snapshot)
        self.session.teach(outcome, "binary_search", question=question)
        gap = self.session.current_gap()
        self.assertIsNotNone(gap)
        self.assertEqual(gap.status, GAP_INTERVENTION_APPLIED)

        # original problem passes after the intervention -> pending transfer, NOT recovered
        self.session.observe(
            {
                "session_id": "TESTS-01",
                "timestamp": "2026-08-17T22:10:00+05:30",
                "event_id": "evt-tests-02",
                "concept": "binary_search",
                "secondary_concepts": [],
                "test_results": {"passed": ["normal", "left_boundary", "single_element"], "failed": []},
                "failure_classes": [],
                "static_pattern": None,
                "recurrence": True,
                "code": "while low < high:\n    if a[mid] < target: low = mid + 1\n    else: high = mid\nreturn low",
            }
        )
        self.session.decide()
        self.session.gaps.mark_original_recovered(gap, {"retry": "passed"})
        self.assertEqual(gap.status, GAP_RECOVERED_PENDING_TRANSFER)
        self.assertFalse(gap.transfer_verified)

        # transfer problem (structurally different) passes -> recovered
        from adaptive.core.gaps import make_transfer_check, select_transfer_problem

        transfer_item = select_transfer_problem(
            self.pack.items,
            "binary_search",
            original_problem_id=event.event_id,
        )
        check = make_transfer_check(
            transfer_item,
            original_problem_id=event.event_id,
            passed=True,
            structurally_different=True,
        )
        self.session.gaps.verify_transfer(gap, check)
        self.assertEqual(gap.status, GAP_RECOVERED)
        self.assertTrue(gap.transfer_verified)

    def test_abstention_when_evidence_thin(self):
        self.session.observe(
            {
                "session_id": "TESTS-01",
                "timestamp": "2026-08-17T22:00:00+05:30",
                "event_id": "evt-tests-03",
                "concept": "binary_search",
                "secondary_concepts": ["boundary_handling"],
                "test_results": {"passed": ["normal"], "failed": ["single_element"]},
                "failure_classes": ["single_element"],
                "static_pattern": "off_by_one_bound",
                "recurrence": False,
                "code": "while low < high: low = mid",
            }
        )
        snapshot = self.session.diagnose()
        self.assertTrue(snapshot.insufficient)
        self.assertIsNone(snapshot.selected_question)


    def test_no_duplicate_questions_in_session(self):
        self.session.observe(self._failed_submission(["left_boundary", "single_element"], "low_mid_no_increment", True))
        seen_questions = set()

        for turn in range(5):
            snap = self.session.diagnose()
            if snap.selected_question:
                qid = snap.selected_question.id
                self.assertNotIn(qid, seen_questions, f"Question '{qid}' was selected twice in turn {turn}")
                seen_questions.add(qid)
                self.session.answer_diagnostic(snap.selected_question, 0)

        self.assertGreaterEqual(len(seen_questions), 2, "Session should have selected multiple distinct questions across turns")


if __name__ == "__main__":
    unittest.main()
