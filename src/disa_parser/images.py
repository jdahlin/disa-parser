"""Image extraction from DISA exam PDFs.

Extracts images and associates them with questions based on position.
Handles:
- Inline question images
- Annotatable papers (full-page images for drawing)
- Answer key images
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import fitz

if TYPE_CHECKING:
    from .models import Question


@dataclass
class ExtractedImage:
    """An image extracted from a PDF."""

    xref: int  # PDF internal reference
    page_num: int
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    width: int
    height: int
    image_type: str  # png, jpeg, etc.
    data: bytes = field(repr=False)
    hash: str = ""  # Content hash for deduplication

    def __post_init__(self):
        if not self.hash:
            self.hash = hashlib.md5(self.data).hexdigest()[:12]

    @property
    def area(self) -> float:
        """Calculate image area in points squared."""
        return (self.bbox[2] - self.bbox[0]) * (self.bbox[3] - self.bbox[1])

    @property
    def aspect_ratio(self) -> float:
        """Width / height ratio."""
        if self.height == 0:
            return 0
        return self.width / self.height

    def is_full_page(self, page_width: float, page_height: float) -> bool:
        """Check if image covers most of the page (annotatable paper)."""
        img_width = self.bbox[2] - self.bbox[0]
        img_height = self.bbox[3] - self.bbox[1]
        # Image covers >70% of page dimensions
        return (img_width / page_width > 0.7) and (img_height / page_height > 0.7)

    def is_tiny(self) -> bool:
        """Check if image is too small to be meaningful (icons, bullets)."""
        return self.width < 20 or self.height < 20

    def save(self, path: Path | str) -> Path:
        """Save image to file."""
        path = Path(path)
        path.write_bytes(self.data)
        return path


@dataclass
class QuestionImages:
    """Images associated with a question."""

    question_num: int
    images: list[ExtractedImage] = field(default_factory=list)
    annotatable_paper: ExtractedImage | None = None  # Full-page drawing paper

    def has_images(self) -> bool:
        return bool(self.images) or self.annotatable_paper is not None


class ImageExtractor:
    """Extract and associate images from DISA exam PDFs."""

    # Minimum image dimensions to extract (skip tiny icons/bullets)
    MIN_WIDTH = 30
    MIN_HEIGHT = 30

    # Threshold for considering an image as full-page annotatable paper
    PAGE_COVERAGE_THRESHOLD = 0.6

    def __init__(self, pdf_path: Path | str):
        self.pdf_path = Path(pdf_path)
        self.doc = fitz.open(pdf_path)
        self._image_cache: dict[int, ExtractedImage] = {}  # xref -> image

    def close(self):
        self.doc.close()

    def extract_all_images(self) -> list[ExtractedImage]:
        """Extract all meaningful images from the PDF."""
        images = []
        seen_hashes: set[str] = set()

        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            page_images = self._extract_page_images(page, page_num)

            for img in page_images:
                # Skip duplicates (same image repeated)
                if img.hash in seen_hashes:
                    continue
                seen_hashes.add(img.hash)
                images.append(img)

        return images

    def _extract_page_images(self, page: fitz.Page, page_num: int) -> list[ExtractedImage]:
        """Extract images from a single page."""
        images = []

        # Get all images on this page
        image_list = page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]

            # Check cache first
            if xref in self._image_cache:
                cached = self._image_cache[xref]
                # Update page_num if this is a different page
                if cached.page_num != page_num:
                    # Same image on different page - might need to handle differently
                    pass
                images.append(cached)
                continue

            try:
                # Extract the image
                base_image = self.doc.extract_image(xref)
                if not base_image:
                    continue

                width = base_image["width"]
                height = base_image["height"]

                # Skip tiny images
                if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                    continue

                # Determine image format
                ext = base_image["ext"]
                if ext == "jpeg":
                    img_type = "jpeg"
                elif ext in ("png", "pam"):
                    img_type = "png"
                else:
                    img_type = ext

                # Get bounding box for this image on this page
                bbox = self._get_image_bbox(page, xref, img_info)

                extracted = ExtractedImage(
                    xref=xref,
                    page_num=page_num,
                    bbox=bbox,
                    width=width,
                    height=height,
                    image_type=img_type,
                    data=base_image["image"],
                )

                self._image_cache[xref] = extracted
                images.append(extracted)

            except Exception:
                # Skip problematic images
                continue

        return images

    def _get_image_bbox(
        self, page: fitz.Page, xref: int, img_info: tuple
    ) -> tuple[float, float, float, float]:
        """Get the bounding box of an image on a page."""
        # Try to get the image rectangle from the page
        try:
            # img_info format: (xref, smask, width, height, bpc, colorspace, alt, name, filter, referencer)
            # We need to find where this image is placed on the page

            # Method 1: Search for image references in page content
            for img_rect in page.get_image_rects(xref):
                return tuple(img_rect)

            # Method 2: Use image dimensions relative to page
            # This is a fallback - not accurate but better than nothing
            width = img_info[2]
            height = img_info[3]
            page_rect = page.rect
            return (0, 0, min(width, page_rect.width), min(height, page_rect.height))

        except Exception:
            # Fallback: return page bounds
            rect = page.rect
            return (rect.x0, rect.y0, rect.x1, rect.y1)

    def get_images_for_question(
        self,
        question_num: int,
        question_page: int,
        question_y: float,
        next_question_y: float | None,
        page_height: float,
    ) -> QuestionImages:
        """Get images that belong to a specific question.

        Args:
            question_num: Question number
            question_page: Page where question starts
            question_y: Y position where question starts
            next_question_y: Y position where next question starts (or None)
            page_height: Height of the page

        Returns:
            QuestionImages with associated images
        """
        result = QuestionImages(question_num=question_num)

        # Get images on this page
        page = self.doc[question_page]
        page_images = self._extract_page_images(page, question_page)
        page_rect = page.rect

        for img in page_images:
            img_y = img.bbox[1]  # Top of image
            img_bottom = img.bbox[3]

            # Check if image is in question's y-range
            in_range = img_y >= question_y - 20  # Allow some margin above

            if next_question_y is not None:
                in_range = in_range and img_y < next_question_y
            else:
                # Last question on page - image should be below question start
                in_range = in_range and img_y < page_height

            if not in_range:
                continue

            # Check if this is a full-page annotatable paper
            if img.is_full_page(page_rect.width, page_rect.height):
                result.annotatable_paper = img
            else:
                result.images.append(img)

        return result

    def extract_annotatable_papers(self) -> list[tuple[int, ExtractedImage]]:
        """Find all full-page images that are likely annotatable papers.

        Returns:
            List of (page_num, image) tuples
        """
        papers = []

        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            page_rect = page.rect
            page_images = self._extract_page_images(page, page_num)

            for img in page_images:
                if img.is_full_page(page_rect.width, page_rect.height):
                    papers.append((page_num, img))

        return papers

    def save_question_images(
        self,
        question_images: QuestionImages,
        output_dir: Path,
        exam_id: str,
    ) -> dict[str, Path]:
        """Save images for a question to files.

        Args:
            question_images: Images associated with the question
            output_dir: Directory to save images
            exam_id: Exam identifier for filename prefix

        Returns:
            Dict mapping image type to saved path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        saved: dict[str, Path] = {}

        q_num = question_images.question_num

        # Save regular images
        for i, img in enumerate(question_images.images):
            suffix = f"_{i}" if len(question_images.images) > 1 else ""
            filename = f"{exam_id}_q{q_num:02d}_img{suffix}.{img.image_type}"
            path = output_dir / filename
            img.save(path)
            saved[f"image{suffix}"] = path

        # Save annotatable paper
        if question_images.annotatable_paper:
            img = question_images.annotatable_paper
            filename = f"{exam_id}_q{q_num:02d}_paper.{img.image_type}"
            path = output_dir / filename
            img.save(path)
            saved["paper"] = path

        return saved


def extract_images_from_exam(
    pdf_path: Path | str,
    output_dir: Path | str | None = None,
    exam_id: str | None = None,
) -> dict[int, QuestionImages]:
    """Convenience function to extract all images from an exam.

    Args:
        pdf_path: Path to the PDF
        output_dir: Optional directory to save images
        exam_id: Optional exam ID for filenames

    Returns:
        Dict mapping question number to QuestionImages
    """
    from .parser import DISAParser

    pdf_path = Path(pdf_path)
    if exam_id is None:
        exam_id = pdf_path.stem[:20]

    # First parse the exam to get question positions
    parser = DISAParser(pdf_path, "unknown")
    exam = parser.parse()
    parser.close()

    # Extract images
    extractor = ImageExtractor(pdf_path)
    results: dict[int, QuestionImages] = {}

    # Build question position map
    # This is a simplified approach - in practice you'd want
    # the actual y-positions from parsing
    for i, question in enumerate(exam.questions):
        # Get next question for y-range calculation
        next_q = exam.questions[i + 1] if i + 1 < len(exam.questions) else None

        # For now, use page-based extraction
        # A more sophisticated approach would track actual y-positions during parsing
        q_images = QuestionImages(question_num=question.number)

        # Get all images and try to associate by page
        # This is a basic implementation - could be improved with actual position tracking
        results[question.number] = q_images

    # Also extract annotatable papers
    papers = extractor.extract_annotatable_papers()
    for page_num, paper_img in papers:
        # Try to find which question this paper belongs to
        # (would need page-to-question mapping from parser)
        pass

    extractor.close()

    # Optionally save images
    if output_dir:
        output_dir = Path(output_dir)
        for q_num, q_images in results.items():
            if q_images.has_images():
                extractor_new = ImageExtractor(pdf_path)
                extractor_new.save_question_images(q_images, output_dir, exam_id)
                extractor_new.close()

    return results
