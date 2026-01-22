"""Test that parser output matches expected YAML fixtures."""

import os
from pathlib import Path

import pytest
import yaml

from src.disa_parser.constants import TYPE_CODES
from src.disa_parser.fixture import load_fixture
from src.disa_parser.parser import DISAParser


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "questions"


def get_fixture_pairs():
    """Get all JSON/YAML fixture pairs."""
    pairs = []
    for json_file in FIXTURE_DIR.glob("*.json"):
        yaml_file = json_file.with_suffix(".expected.yaml")
        if yaml_file.exists():
            pairs.append((json_file, yaml_file))
    return pairs


def parse_fixture_to_dict(json_path: Path) -> dict:
    """Parse a JSON fixture and return the expected YAML structure."""
    fixture = load_fixture(str(json_path))
    parser = DISAParser("test.pdf", "test", fixture=fixture)
    exam = parser.parse()
    parser.close()

    questions = []
    for q in exam.questions:
        qtype = TYPE_CODES.get(q.question_type, "unk")
        qdata = {
            "num": q.number,
            "type": qtype,
            "type_full": q.question_type,
            "pts": q.points,
            "text": q.text,
        }
        if q.category:
            qdata["cat"] = q.category
        if q.expected_answers != 1:
            qdata["expected_answers"] = q.expected_answers
        if q.options:
            qdata["opts"] = [
                {"text": o.text, "correct": True} if o.is_correct else {"text": o.text}
                for o in q.options
            ]
        if q.answer:
            qdata["answer"] = q.answer
        questions.append(qdata)

    return {"questions": questions}


@pytest.mark.parametrize(
    "json_path,yaml_path",
    get_fixture_pairs(),
    ids=[p[0].stem for p in get_fixture_pairs()],
)
def test_parser_output_matches_expected(json_path: Path, yaml_path: Path):
    """Verify parser output matches expected YAML for each fixture."""
    # Parse the JSON fixture
    actual = parse_fixture_to_dict(json_path)

    # Load expected YAML
    with open(yaml_path, encoding="utf-8") as f:
        expected = yaml.safe_load(f)

    # Compare
    assert actual == expected, f"Parser output differs from {yaml_path.name}"


def test_all_fixtures_have_expected_yaml():
    """Ensure every JSON fixture has a corresponding expected YAML file."""
    json_files = list(FIXTURE_DIR.glob("*.json"))
    missing = []
    for json_file in json_files:
        yaml_file = json_file.with_suffix(".expected.yaml")
        if not yaml_file.exists():
            missing.append(json_file.name)

    assert not missing, f"Missing expected YAML files for: {missing}"
