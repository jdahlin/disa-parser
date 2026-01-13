"""Tests for the fixture module."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from disa_parser import FixtureEncoder, MockDocument, MockPage, load_fixture


class TestMockPage:
    """Tests for MockPage."""

    def test_get_text_dict(self, sample_fixture_data: dict):
        """Test getting text as dict."""
        page_data = sample_fixture_data["pages"]["0"]
        page = MockPage(page_data)
        text_dict = page.get_text("dict")
        assert "blocks" in text_dict
        assert len(text_dict["blocks"]) > 0

    def test_get_text_plain(self, sample_fixture_data: dict):
        """Test getting plain text."""
        page_data = sample_fixture_data["pages"]["0"]
        page = MockPage(page_data)
        text = page.get_text()
        assert "TENTAMEN" in text

    def test_get_drawings(self, mcq_fixture_data: dict):
        """Test getting drawings."""
        page_data = mcq_fixture_data["pages"]["3"]
        page = MockPage(page_data)
        drawings = page.get_drawings()
        assert len(drawings) == 1
        assert drawings[0]["fill"] == (0.1, 0.6, 0.1)

    def test_empty_page(self):
        """Test empty page."""
        page = MockPage({"text_dict": {"blocks": []}, "drawings": []})
        assert page.get_text() == ""
        assert page.get_drawings() == []


class TestMockDocument:
    """Tests for MockDocument."""

    def test_len(self, sample_fixture_data: dict):
        """Test document length."""
        doc = MockDocument(sample_fixture_data)
        assert len(doc) == 10

    def test_getitem(self, sample_fixture_data: dict):
        """Test page access by index."""
        doc = MockDocument(sample_fixture_data)
        page = doc[0]
        assert isinstance(page, MockPage)
        text = page.get_text()
        assert "TENTAMEN" in text

    def test_getitem_missing_page(self, sample_fixture_data: dict):
        """Test accessing page not in fixture returns empty page."""
        doc = MockDocument(sample_fixture_data)
        page = doc[5]  # Not in fixture
        assert page.get_text() == ""

    def test_close(self, sample_fixture_data: dict):
        """Test close method (should be no-op)."""
        doc = MockDocument(sample_fixture_data)
        doc.close()  # Should not raise


class TestLoadFixture:
    """Tests for load_fixture function."""

    def test_load_from_dict(self, sample_fixture_data: dict):
        """Test loading from dict."""
        doc = load_fixture(sample_fixture_data)
        assert isinstance(doc, MockDocument)
        assert len(doc) == 10

    def test_load_from_json_string(self, sample_fixture_data: dict):
        """Test loading from JSON string."""
        json_str = json.dumps(sample_fixture_data)
        doc = load_fixture(json_str)
        assert isinstance(doc, MockDocument)
        assert len(doc) == 10

    def test_load_from_file(self, sample_fixture_data: dict):
        """Test loading from file path."""
        with TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "fixture.json"
            filepath.write_text(json.dumps(sample_fixture_data))
            doc = load_fixture(filepath)
            assert isinstance(doc, MockDocument)
            assert len(doc) == 10


class TestFixtureEncoder:
    """Tests for FixtureEncoder."""

    def test_encode_bytes(self):
        """Test encoding bytes."""
        data = {"binary": b"hello"}
        result = json.dumps(data, cls=FixtureEncoder)
        decoded = json.loads(result)
        assert "__bytes__" in decoded["binary"]

    def test_encode_tuple(self):
        """Test encoding tuples (rects)."""
        data = {"rect": (1.0, 2.0, 3.0, 4.0)}
        result = json.dumps(data, cls=FixtureEncoder)
        decoded = json.loads(result)
        assert decoded["rect"] == [1.0, 2.0, 3.0, 4.0]
