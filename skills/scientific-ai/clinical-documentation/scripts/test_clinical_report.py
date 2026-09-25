"""Offline regressions for citation repair; no clinical model calls."""
import tempfile
import json
import unittest
from pathlib import Path

from clinical_report import document_transcript, ContextBudgetExceeded


class CitationReporter:
    def __init__(self, initial='unclear', relocated=True, repaired='supported'):
        self.initial, self.relocated, self.repaired = initial, relocated, repaired
        self.calls = []

    def complete(self, stage, prompt, data):
        self.calls.append((stage, data))
        if stage.startswith('extract'):
            return {'kind': 'consultation', 'facts': [
                {'section': 'history', 'statement': 'Symptoms began yesterday.',
                 'source_phrases': [{'source_id': 'S1', 'quote': 'Symptoms began yesterday.'}],
                 'source_ids': ['S1'], 'uncertain': False, 'medication_or_dose': False, 'source_anchors': []},
                {'section': 'plan', 'statement': 'A sample may be collected if symptoms persist.',
                 'source_phrases': [{'source_id': 'S2', 'quote': 'A sample may be collected if symptoms persist.'}],
                 'source_ids': ['S2'], 'uncertain': False, 'medication_or_dose': False, 'source_anchors': []}], 'uncertainties': []}
        if stage.startswith('review'):
            fact = data['facts'][0]
            verdict = ('supported' if fact['id'] == 'F0001' else
                       self.repaired if stage.endswith('-repaired') else self.initial)
            return {'decisions': [{'id': fact['id'], 'verdict': verdict,
                'reason': 'Exact cited source checked; incomplete evidence is not approval.',
                'medication_or_dose': False, 'source_anchors': []}]}
        if stage.startswith('locate'):
            return {'source_ids': ['S1', 'S2'] if self.relocated else []}
        if stage == 'questions':
            return {'questions': []}
        raise AssertionError(stage)


class CitationRepairTests(unittest.TestCase):
    def test_optional_question_budget_failure_saves_full_report_and_explicit_omission(self):
        class QuestionLimitedReporter(CitationReporter):
            def __init__(self):
                super().__init__()
                self.generation_warnings = []
            def complete(self, stage, prompt, data):
                if stage == 'questions':
                    raise ContextBudgetExceeded(stage, {'input_tokens': 7000, 'max_output_tokens': 1800, 'context_tokens': 8192, 'reserve_tokens': 64})
                return super().complete(stage, prompt, data)
        text = 'Symptoms began yesterday. ' + ('Conversation context. ' * 18)
        text += 'A sample may be collected if symptoms persist.'
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            baseline = document_transcript(text, 'en', CitationReporter(), output / 'baseline')
            actual = document_transcript(text, 'en', QuestionLimitedReporter(), output / 'limited')
            self.assertEqual(actual['facts'], baseline['facts'])
            self.assertEqual(actual['transcript_sha256'], baseline['transcript_sha256'])
            self.assertEqual(actual['questions'], [])
            self.assertEqual(actual['generation_warnings'][0]['code'], 'optional_questions_context_budget_exceeded')
            saved = json.loads((output / 'limited/review.json').read_text())
            self.assertEqual(saved['generation_warnings'], actual['generation_warnings'])
            self.assertIn('GENERATION INCOMPLETENESS', (output / 'limited/report.md').read_text())
            self.assertIn('No facts were truncated', (output / 'limited/review.md').read_text())

    def run_case(self, reporter):
        text = 'Symptoms began yesterday. ' + ('Conversation context. ' * 18)
        text += 'A sample may be collected if symptoms persist.'
        with tempfile.TemporaryDirectory() as folder:
            return document_transcript(text, 'en', reporter, Path(folder))

    def test_unclear_incomplete_citation_is_relocated_and_reviewed(self):
        reporter = CitationReporter()
        result = self.run_case(reporter)
        fact = next(f for f in result['facts'] if f['id'] == 'F0002')
        self.assertEqual(fact['statement'], 'A sample may be collected if symptoms persist.')
        self.assertEqual([e['source_id'] for e in fact['evidence']], ['S1', 'S2'])
        self.assertEqual([e['source_id'] for e in fact['citation_repair']['original_evidence']], ['S2'])
        self.assertEqual(sum(stage.startswith('locate') for stage, _ in reporter.calls), 1)
        self.assertTrue(any(stage.endswith('-repaired') for stage, _ in reporter.calls))

    def test_unclear_after_relocation_is_not_accepted(self):
        reporter = CitationReporter(repaired='unclear')
        result = self.run_case(reporter)
        self.assertEqual([f['id'] for f in result['facts']], ['F0001'])
        self.assertEqual(result['rejected'][0]['verdict'], 'unclear')
        self.assertIn('citation_repair', result['rejected'][0]['candidate'])

    def test_missing_evidence_never_changes_or_accepts_statement(self):
        reporter = CitationReporter(relocated=False)
        result = self.run_case(reporter)
        self.assertEqual([f['id'] for f in result['facts']], ['F0001'])
        self.assertEqual(result['rejected'][0]['candidate']['statement'],
                         'A sample may be collected if symptoms persist.')
        self.assertFalse(any(stage.endswith('-repaired') for stage, _ in reporter.calls))

    def test_unsupported_citation_keeps_existing_bounded_repair(self):
        reporter = CitationReporter(initial='unsupported')
        result = self.run_case(reporter)
        self.assertEqual(len(result['facts']), 2)
        self.assertEqual(sum(stage.startswith('locate') for stage, _ in reporter.calls), 1)


if __name__ == '__main__':
    unittest.main()
