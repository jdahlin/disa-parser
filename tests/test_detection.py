"""Tests for DISA exam detection functions."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from disa_parser import is_disa_exam, is_merged_exam, is_ungraded_exam, scan_directory


class TestIsUngradedExam:
    """Tests for is_ungraded_exam function."""

    def test_detects_utan_svar(self):
        """Test detection of utan_svar in filename."""
        assert is_ungraded_exam(Path("exam_utan_svar.pdf")) is True
        assert is_ungraded_exam(Path("tentamen_Utan_Svar_2024.pdf")) is True

    def test_normal_exam_not_ungraded(self):
        """Test that normal exams are not flagged as ungraded."""
        assert is_ungraded_exam(Path("exam_med_svar.pdf")) is False
        assert is_ungraded_exam(Path("tentamen_2024.pdf")) is False


class TestIsMergedExam:
    """Tests for is_merged_exam function."""

    def test_detects_merged_filename_patterns(self):
        """Test detection of merged file patterns in filename."""
        assert is_merged_exam(Path("Tentor_med_svar.pdf")) is True
        assert is_merged_exam(Path("exam_samling_2024.pdf")) is True

    def test_normal_exam_not_merged(self):
        """Test that normal exams are not flagged as merged."""
        assert is_merged_exam(Path("tentamen_2024.pdf")) is False
        # Note: PDF content check would require actual PDF files


class TestScanDirectory:
    """Tests for scan_directory function."""

    def test_empty_directory(self):
        """Test scanning empty directory."""
        with TemporaryDirectory() as tmpdir:
            result = scan_directory(tmpdir)
            assert result == []

    def test_nonexistent_directory(self):
        """Test scanning non-existent directory."""
        result = scan_directory(Path("/nonexistent/path"))
        assert result == []

    def test_directory_with_no_pdfs(self):
        """Test scanning directory with no PDF files."""
        with TemporaryDirectory() as tmpdir:
            # Create non-PDF files
            (Path(tmpdir) / "file.txt").write_text("test")
            (Path(tmpdir) / "image.png").write_bytes(b"fake png")
            result = scan_directory(tmpdir)
            assert result == []
