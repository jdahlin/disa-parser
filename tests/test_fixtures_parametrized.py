"""Parametrized tests using per-question fixtures from real exams.

These tests load JSON fixtures extracted from real DISA exam PDFs and verify
that the parser extracts the same data when parsing the fixture.

Fixtures are stored in tests/fixtures/questions/ with naming:
    {course}-{exam_id}-{question_num:02d}.json.gz

To add new fixtures, use:
    uv run scripts/extract_question_fixtures.py path/to/exam.pdf -o tests/fixtures/questions/
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from disa_parser import DISAParser
from disa_parser.fixture import fixture_decoder, load_fixture, MockDocument

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "questions"


def load_question_fixture(fixture_path: Path) -> dict[str, Any]:
    """Load a question fixture file (supports .json and .json.gz)."""
    if fixture_path.suffix == ".gz":
        with gzip.open(fixture_path, "rt", encoding="utf-8") as f:
            return json.load(f, object_hook=fixture_decoder)
    return json.loads(fixture_path.read_text(), object_hook=fixture_decoder)


def discover_fixtures() -> list[tuple[str, Path]]:
    """Discover all question fixtures for parametrization."""
    if not FIXTURES_DIR.exists():
        return []

    fixtures = []
    for fixture_path in sorted(FIXTURES_DIR.glob("*.json.gz")):
        # Create a readable test ID from filename (remove .json.gz)
        test_id = fixture_path.stem.removesuffix(".json")  # e.g., "fysiologi-CiyL1wzjXlQxVHpLMxf7-01"
        fixtures.append((test_id, fixture_path))

    return fixtures


# Discover fixtures at module load time
FIXTURES = discover_fixtures()


@pytest.mark.parametrize("test_id,fixture_path", FIXTURES, ids=[f[0] for f in FIXTURES])
class TestQuestionFixtures:
    """Tests that verify parser output matches expected fixture data."""

    def test_question_number(self, test_id: str, fixture_path: Path):
        """Test that the correct question number is extracted."""
        fixture = load_question_fixture(fixture_path)
        expected = fixture["question"]

        # Create mock document and parse
        mock_doc = self._create_mock_doc(fixture)
        parser = DISAParser(Path(fixture["source"]), fixture["course"], fixture=mock_doc)
        exam = parser.parse()
        parser.close()

        # Find the expected question
        question = self._find_question(exam.questions, expected["number"])
        assert question is not None, f"Question {expected['number']} not found"
        assert question.number == expected["number"]

    def test_question_type(self, test_id: str, fixture_path: Path):
        """Test that the question type is correctly identified."""
        fixture = load_question_fixture(fixture_path)
        expected = fixture["question"]

        mock_doc = self._create_mock_doc(fixture)
        parser = DISAParser(Path(fixture["source"]), fixture["course"], fixture=mock_doc)
        exam = parser.parse()
        parser.close()

        question = self._find_question(exam.questions, expected["number"])
        assert question is not None, f"Question {expected['number']} not found"
        assert question.question_type == expected["type"], (
            f"Expected type '{expected['type']}', got '{question.question_type}'"
        )

    def test_question_text(self, test_id: str, fixture_path: Path):
        """Test that question text is extracted correctly."""
        fixture = load_question_fixture(fixture_path)
        expected = fixture["question"]

        mock_doc = self._create_mock_doc(fixture)
        parser = DISAParser(Path(fixture["source"]), fixture["course"], fixture=mock_doc)
        exam = parser.parse()
        parser.close()

        question = self._find_question(exam.questions, expected["number"])
        assert question is not None, f"Question {expected['number']} not found"

        # Text should contain the expected text (may have slight formatting differences)
        # Use substring match to handle whitespace/formatting variations
        expected_text = expected["text"][:50]  # First 50 chars
        assert expected_text in question.text or question.text in expected["text"], (
            f"Text mismatch:\nExpected: {expected['text'][:100]}...\nGot: {question.text[:100]}..."
        )

    def test_question_points(self, test_id: str, fixture_path: Path):
        """Test that points are extracted correctly."""
        fixture = load_question_fixture(fixture_path)
        expected = fixture["question"]

        mock_doc = self._create_mock_doc(fixture)
        parser = DISAParser(Path(fixture["source"]), fixture["course"], fixture=mock_doc)
        exam = parser.parse()
        parser.close()

        question = self._find_question(exam.questions, expected["number"])
        assert question is not None, f"Question {expected['number']} not found"
        assert question.points == expected["points"], (
            f"Expected {expected['points']} points, got {question.points}"
        )

    def test_options_count(self, test_id: str, fixture_path: Path):
        """Test that the correct number of options are extracted."""
        fixture = load_question_fixture(fixture_path)
        expected = fixture["question"]

        if not expected["options"]:
            pytest.skip("Question has no options")

        mock_doc = self._create_mock_doc(fixture)
        parser = DISAParser(Path(fixture["source"]), fixture["course"], fixture=mock_doc)
        exam = parser.parse()
        parser.close()

        question = self._find_question(exam.questions, expected["number"])
        assert question is not None, f"Question {expected['number']} not found"
        assert len(question.options) == len(expected["options"]), (
            f"Expected {len(expected['options'])} options, got {len(question.options)}"
        )

    def test_correct_options_marked(self, test_id: str, fixture_path: Path):
        """Test that correct options are properly marked."""
        fixture = load_question_fixture(fixture_path)
        expected = fixture["question"]

        expected_correct = [o for o in expected["options"] if o["is_correct"]]
        if not expected_correct:
            pytest.skip("No correct options marked in fixture")

        mock_doc = self._create_mock_doc(fixture)
        parser = DISAParser(Path(fixture["source"]), fixture["course"], fixture=mock_doc)
        exam = parser.parse()
        parser.close()

        question = self._find_question(exam.questions, expected["number"])
        assert question is not None, f"Question {expected['number']} not found"

        actual_correct = [o for o in question.options if o.is_correct]
        expected_count = len(expected_correct)
        actual_count = len(actual_correct)

        assert actual_count == expected_count, (
            f"Expected {expected_count} correct options, got {actual_count}"
        )

    def test_answer_extracted(self, test_id: str, fixture_path: Path):
        """Test that answer text is extracted for essay/text questions."""
        fixture = load_question_fixture(fixture_path)
        expected = fixture["question"]

        if not expected["answer"]:
            pytest.skip("No answer in fixture")

        mock_doc = self._create_mock_doc(fixture)
        parser = DISAParser(Path(fixture["source"]), fixture["course"], fixture=mock_doc)
        exam = parser.parse()
        parser.close()

        question = self._find_question(exam.questions, expected["number"])
        assert question is not None, f"Question {expected['number']} not found"

        # Answer should match (allowing for some variation)
        assert question.answer, "No answer extracted"
        # At least some overlap expected
        expected_start = expected["answer"][:20]
        assert expected_start in question.answer or question.answer[:20] in expected["answer"]

    def _create_mock_doc(self, fixture: dict) -> MockDocument:
        """Create a MockDocument from fixture data."""
        return MockDocument({
            "page_count": fixture["page_count"],
            "pages": fixture["pages"],
        })

    def _find_question(self, questions: list, number: int):
        """Find a question by number."""
        for q in questions:
            if q.number == number:
                return q
        return None


# Standalone function-based tests for quick validation
def test_fixtures_exist():
    """Verify that fixture files exist for testing."""
    if not FIXTURES_DIR.exists():
        pytest.skip(f"Fixtures directory not found: {FIXTURES_DIR}")

    fixtures = list(FIXTURES_DIR.glob("*.json.gz"))
    assert len(fixtures) > 0, "No fixture files found"
    print(f"Found {len(fixtures)} fixture files")


def test_fixture_format():
    """Verify fixture files have correct structure."""
    if not FIXTURES_DIR.exists():
        pytest.skip(f"Fixtures directory not found: {FIXTURES_DIR}")

    for fixture_path in list(FIXTURES_DIR.glob("*.json.gz"))[:3]:  # Check first 3
        fixture = load_question_fixture(fixture_path)

        assert "source" in fixture, f"Missing 'source' in {fixture_path.name}"
        assert "exam_id" in fixture, f"Missing 'exam_id' in {fixture_path.name}"
        assert "course" in fixture, f"Missing 'course' in {fixture_path.name}"
        assert "page_count" in fixture, f"Missing 'page_count' in {fixture_path.name}"
        assert "question" in fixture, f"Missing 'question' in {fixture_path.name}"
        assert "pages" in fixture, f"Missing 'pages' in {fixture_path.name}"

        q = fixture["question"]
        assert "number" in q, f"Missing question.number in {fixture_path.name}"
        assert "type" in q, f"Missing question.type in {fixture_path.name}"
        assert "text" in q, f"Missing question.text in {fixture_path.name}"
