"""Tests for image extraction."""

from __future__ import annotations

import pytest

from disa_parser import ImageRef
from disa_parser.images import ExtractedImage, QuestionImages


class TestExtractedImage:
    """Tests for ExtractedImage dataclass."""

    def test_create_image(self):
        """Test creating an extracted image."""
        img = ExtractedImage(
            xref=1,
            page_num=0,
            bbox=(10, 20, 100, 120),
            width=90,
            height=100,
            image_type="png",
            data=b"fake image data",
        )
        assert img.xref == 1
        assert img.page_num == 0
        assert img.width == 90
        assert img.height == 100
        assert img.image_type == "png"
        assert len(img.hash) == 12  # MD5 hash truncated

    def test_area_calculation(self):
        """Test area calculation."""
        img = ExtractedImage(
            xref=1,
            page_num=0,
            bbox=(0, 0, 100, 50),
            width=100,
            height=50,
            image_type="png",
            data=b"x",
        )
        assert img.area == 5000

    def test_aspect_ratio(self):
        """Test aspect ratio calculation."""
        img = ExtractedImage(
            xref=1,
            page_num=0,
            bbox=(0, 0, 100, 50),
            width=200,
            height=100,
            image_type="png",
            data=b"x",
        )
        assert img.aspect_ratio == 2.0

    def test_is_full_page(self):
        """Test full page detection."""
        img = ExtractedImage(
            xref=1,
            page_num=0,
            bbox=(0, 0, 580, 800),
            width=580,
            height=800,
            image_type="png",
            data=b"x",
        )
        # 580/600 = 0.97, 800/850 = 0.94 - both > 0.7
        assert img.is_full_page(600, 850) is True

    def test_is_not_full_page(self):
        """Test non-full page image."""
        img = ExtractedImage(
            xref=1,
            page_num=0,
            bbox=(0, 0, 100, 100),
            width=100,
            height=100,
            image_type="png",
            data=b"x",
        )
        # 100/600 = 0.17 - not full page
        assert img.is_full_page(600, 850) is False

    def test_is_tiny(self):
        """Test tiny image detection."""
        img = ExtractedImage(
            xref=1,
            page_num=0,
            bbox=(0, 0, 10, 10),
            width=10,
            height=10,
            image_type="png",
            data=b"x",
        )
        assert img.is_tiny() is True

    def test_is_not_tiny(self):
        """Test non-tiny image."""
        img = ExtractedImage(
            xref=1,
            page_num=0,
            bbox=(0, 0, 100, 100),
            width=100,
            height=100,
            image_type="png",
            data=b"x",
        )
        assert img.is_tiny() is False


class TestQuestionImages:
    """Tests for QuestionImages dataclass."""

    def test_create_empty(self):
        """Test creating empty question images."""
        qi = QuestionImages(question_num=1)
        assert qi.question_num == 1
        assert qi.images == []
        assert qi.annotatable_paper is None
        assert qi.has_images() is False

    def test_has_images_with_images(self):
        """Test has_images with images present."""
        img = ExtractedImage(
            xref=1,
            page_num=0,
            bbox=(0, 0, 100, 100),
            width=100,
            height=100,
            image_type="png",
            data=b"x",
        )
        qi = QuestionImages(question_num=1, images=[img])
        assert qi.has_images() is True

    def test_has_images_with_paper(self):
        """Test has_images with annotatable paper."""
        paper = ExtractedImage(
            xref=1,
            page_num=0,
            bbox=(0, 0, 600, 800),
            width=600,
            height=800,
            image_type="png",
            data=b"x",
        )
        qi = QuestionImages(question_num=1, annotatable_paper=paper)
        assert qi.has_images() is True


class TestImageRef:
    """Tests for ImageRef model."""

    def test_create_image_ref(self):
        """Test creating an image reference."""
        ref = ImageRef(
            path="exam_q01_img.png",
            width=200,
            height=150,
            image_type="png",
            is_annotatable_paper=False,
        )
        assert ref.path == "exam_q01_img.png"
        assert ref.width == 200
        assert ref.height == 150

    def test_to_dict(self):
        """Test converting to dictionary."""
        ref = ImageRef(
            path="exam_q01_paper.jpeg",
            width=600,
            height=800,
            image_type="jpeg",
            is_annotatable_paper=True,
        )
        d = ref.to_dict()
        assert d["path"] == "exam_q01_paper.jpeg"
        assert d["width"] == 600
        assert d["height"] == 800
        assert d["type"] == "jpeg"
        assert d["is_paper"] is True
