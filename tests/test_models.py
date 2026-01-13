"""Tests for data models."""

from __future__ import annotations

import pytest

from disa_parser import ExamMetadata, Option, ParsedExam, Question, QuestionType


class TestOption:
    """Tests for the Option model."""

    def test_create_option(self):
        """Test creating a basic option."""
        opt = Option(text="Test option")
        assert opt.text == "Test option"
        assert opt.is_correct is False

    def test_create_correct_option(self):
        """Test creating a correct option."""
        opt = Option(text="Correct answer", is_correct=True)
        assert opt.text == "Correct answer"
        assert opt.is_correct is True


class TestQuestion:
    """Tests for the Question model."""

    def test_create_question(self):
        """Test creating a basic question."""
        q = Question(number=1, text="What is 2+2?", question_type="Flervalsfråga")
        assert q.number == 1
        assert q.text == "What is 2+2?"
        assert q.question_type == "Flervalsfråga"
        assert q.points == 0
        assert q.options == []
        assert q.answer == ""

    def test_question_with_points(self):
        """Test question with points."""
        q = Question(
            number=1,
            text="Question text",
            question_type="Essä",
            points=2.5,
        )
        assert q.points == 2.5

    def test_question_with_options(self):
        """Test question with options."""
        opts = [
            Option(text="A", is_correct=False),
            Option(text="B", is_correct=True),
            Option(text="C", is_correct=False),
        ]
        q = Question(
            number=1,
            text="Pick the correct answer",
            question_type="Flervalsfråga",
            options=opts,
        )
        assert len(q.options) == 3
        assert q.options[1].is_correct is True

    def test_has_answer_with_answer_text(self):
        """Test has_answer returns True when answer text is set."""
        q = Question(number=1, text="Q", question_type="Essä", answer="The answer")
        assert q.has_answer() is True

    def test_has_answer_with_correct_answer(self):
        """Test has_answer returns True when correct_answer is set."""
        q = Question(
            number=1, text="Q", question_type="Flervalsfråga", correct_answer="Option A"
        )
        assert q.has_answer() is True

    def test_has_answer_with_correct_option(self):
        """Test has_answer returns True when an option is marked correct."""
        opts = [Option(text="A", is_correct=True)]
        q = Question(number=1, text="Q", question_type="Flervalsfråga", options=opts)
        assert q.has_answer() is True

    def test_has_answer_false_when_no_answer(self):
        """Test has_answer returns False when no answer data."""
        q = Question(number=1, text="Q", question_type="Essä")
        assert q.has_answer() is False

    def test_to_dict(self):
        """Test converting question to dict."""
        q = Question(
            number=1,
            text="What is 2+2?",
            question_type="Flervalsfråga",
            points=1.0,
            category="Math",
        )
        d = q.to_dict()
        assert d["number"] == 1
        assert d["text"] == "What is 2+2?"
        assert d["type"] == "Flervalsfråga"
        assert d["points"] == 1.0
        assert d["category"] == "Math"

    def test_to_dict_with_options(self):
        """Test converting question with options to dict."""
        opts = [
            Option(text="3", is_correct=False),
            Option(text="4", is_correct=True),
        ]
        q = Question(
            number=1,
            text="What is 2+2?",
            question_type="Flervalsfråga",
            options=opts,
        )
        d = q.to_dict()
        assert len(d["options"]) == 2
        assert d["options"][1]["is_correct"] is True
        assert d["correct"] == ["4"]


class TestExamMetadata:
    """Tests for the ExamMetadata model."""

    def test_create_metadata(self):
        """Test creating exam metadata."""
        meta = ExamMetadata(
            course_code="BIO123",
            exam_title="Introduction to Biology",
            date="01.01.2024",
            is_graded=True,
        )
        assert meta.course_code == "BIO123"
        assert meta.exam_title == "Introduction to Biology"
        assert meta.date == "01.01.2024"
        assert meta.is_graded is True

    def test_default_values(self):
        """Test default values for metadata."""
        meta = ExamMetadata()
        assert meta.course_code == ""
        assert meta.exam_title == ""
        assert meta.date == ""
        assert meta.is_graded is False


class TestParsedExam:
    """Tests for the ParsedExam model."""

    def test_create_parsed_exam(self):
        """Test creating a parsed exam."""
        meta = ExamMetadata(course_code="BIO123")
        questions = [
            Question(number=1, text="Q1", question_type="Essä"),
            Question(number=2, text="Q2", question_type="Flervalsfråga"),
        ]
        exam = ParsedExam(
            filename="exam.pdf",
            course="biokemi",
            metadata=meta,
            questions=questions,
        )
        assert exam.filename == "exam.pdf"
        assert exam.course == "biokemi"
        assert len(exam.questions) == 2

    def test_to_dict(self):
        """Test converting parsed exam to dict."""
        meta = ExamMetadata(course_code="BIO123")
        questions = [Question(number=1, text="Q1", question_type="Essä")]
        exam = ParsedExam(
            filename="exam.pdf",
            course="biokemi",
            metadata=meta,
            questions=questions,
        )
        d = exam.to_dict()
        assert d["filename"] == "exam.pdf"
        assert d["course"] == "biokemi"
        assert d["total_questions"] == 1
        assert len(d["questions"]) == 1


class TestQuestionType:
    """Tests for the QuestionType enum."""

    def test_enum_values(self):
        """Test enum values are strings."""
        assert QuestionType.ESSÄ.value == "Essäfråga"
        assert QuestionType.FLERVALSFRÅGA.value == "Flervalsfråga"
        assert QuestionType.SANT_FALSKT.value == "Sant/Falskt"

    def test_enum_is_string(self):
        """Test enum inherits from str."""
        assert isinstance(QuestionType.ESSÄ, str)
