"""Tests for the DISAParser."""

from __future__ import annotations

from pathlib import Path

import pytest

from disa_parser import DISAParser, MockDocument, load_fixture


class TestDISAParser:
    """Tests for DISAParser."""

    def test_parse_with_fixture(self, mock_document: MockDocument):
        """Test parsing with a mock document fixture."""
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=mock_document)
        result = parser.parse()
        parser.close()

        assert result.course == "biokemi"
        assert result.filename == "test.pdf"

    def test_parse_returns_parsed_exam(self, mock_document: MockDocument):
        """Test that parse returns a ParsedExam object."""
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=mock_document)
        result = parser.parse()
        parser.close()

        assert hasattr(result, "questions")
        assert hasattr(result, "metadata")
        assert hasattr(result, "course")

    def test_to_dict(self, mock_document: MockDocument):
        """Test converting parsed exam to dict."""
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=mock_document)
        result = parser.parse()
        parser.close()

        d = result.to_dict()
        assert "filename" in d
        assert "course" in d
        assert "metadata" in d
        assert "questions" in d
        assert "total_questions" in d

    def test_context_manager_pattern(self, mock_document: MockDocument):
        """Test using parser with explicit close."""
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=mock_document)
        try:
            result = parser.parse()
            assert result is not None
        finally:
            parser.close()

    def test_close_is_idempotent(self, mock_document: MockDocument):
        """Test that calling close multiple times is safe."""
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=mock_document)
        parser.parse()
        parser.close()
        parser.close()  # Should not raise


class TestFormatDetection:
    """Tests for format detection."""

    def test_detect_tentamen_format(self, sample_fixture_data: dict):
        """Test detecting TENTAMEN format."""
        doc = load_fixture(sample_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)
        parser._detect_format()
        # TENTAMEN should be detected
        assert parser.X_QUESTION_NUMBER == 45
        assert parser.X_OPTION == 70
        parser.close()

    def test_default_format_values(self, sample_fixture_data: dict):
        """Test that format detection sets reasonable defaults."""
        doc = load_fixture(sample_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)
        # Before format detection, should have default values
        assert parser.X_QUESTION_NUMBER == 45
        assert parser.X_OPTION == 70
        parser.close()


class TestMetadataParsing:
    """Tests for metadata parsing."""

    def test_parse_course_code(self, sample_fixture_data: dict):
        """Test extracting course code."""
        doc = load_fixture(sample_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)
        parser._parse_metadata()
        # Fixture has "Kurskod BIO123"
        assert parser.metadata.course_code == "BIO123"
        parser.close()

    def test_metadata_defaults(self, sample_fixture_data: dict):
        """Test metadata has default values before parsing."""
        doc = load_fixture(sample_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)
        # Before parsing
        assert parser.metadata.course_code == ""
        assert parser.metadata.is_graded is False
        parser.close()


class TestQuestionSummary:
    """Tests for question summary/TOC parsing."""

    def test_question_types_dict_initialized(self, mcq_fixture_data: dict):
        """Test that question_types is initialized as dict."""
        doc = load_fixture(mcq_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)
        parser._parse_question_summary()
        assert isinstance(parser.question_types, dict)
        parser.close()


class TestColorDetection:
    """Tests for color detection in drawings."""

    def test_get_green_boxes(self, mcq_fixture_data: dict):
        """Test detecting green boxes from drawings."""
        doc = load_fixture(mcq_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)
        # Page 3 has green boxes in the fixture
        page = doc[3]
        green_boxes = parser._get_green_boxes(page)
        assert len(green_boxes) >= 1
        parser.close()

    def test_get_blue_regions_empty_page(self, sample_fixture_data: dict):
        """Test blue region detection on page without blue drawings."""
        doc = load_fixture(sample_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)
        page = doc[0]
        blue_regions = parser._get_blue_regions(page)
        assert blue_regions == []
        parser.close()


class TestHelperMethods:
    """Tests for parser helper methods."""

    def test_is_header_footer(self, sample_fixture_data: dict):
        """Test header/footer detection."""
        doc = load_fixture(sample_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)

        assert parser._is_header_footer("LPG001") is True
        assert parser._is_header_footer("5/10") is True
        assert parser._is_header_footer("Digital tentamen") is True
        assert parser._is_header_footer("Regular question text") is False
        parser.close()

    def test_is_skippable(self, sample_fixture_data: dict):
        """Test skippable text detection."""
        doc = load_fixture(sample_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)

        assert parser._is_skippable("Ord: 150") is True
        assert parser._is_skippable("Skriv in ditt svar här") is True
        assert parser._is_skippable("123 456") is True
        assert parser._is_skippable("This is a question?") is False
        parser.close()

    def test_looks_like_option(self, sample_fixture_data: dict):
        """Test option text detection."""
        doc = load_fixture(sample_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)

        # Single letters should be valid options (image-based MCQ)
        assert parser._looks_like_option("A") is True
        assert parser._looks_like_option("B") is True
        # Very short text
        assert parser._looks_like_option("ab") is False
        # Instruction text
        assert parser._looks_like_option("Välj ett alternativ") is False
        # Normal option text
        assert parser._looks_like_option("This could be an answer option") is True
        parser.close()

    def test_clean_question_text(self, sample_fixture_data: dict):
        """Test question text cleaning."""
        doc = load_fixture(sample_fixture_data)
        parser = DISAParser(Path("test.pdf"), "biokemi", fixture=doc)

        # Should remove instruction text
        text = "Question text Välj ett alternativ:"
        cleaned = parser._clean_question_text(text)
        assert "Välj ett alternativ" not in cleaned

        # Should remove point markers
        text = "Question (2p)"
        cleaned = parser._clean_question_text(text)
        assert "(2p)" not in cleaned
        parser.close()
