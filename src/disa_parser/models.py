"""Data models for DISA exam parsing."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class QuestionType(str, Enum):
    """Question types in DISA exams."""

    FLERVALSFRÅGA = "Flervalsfråga"
    FLERSVARSFRÅGA = "Flersvarsfråga"
    SANT_FALSKT = "Sant/Falskt"
    DRA_OCH_SLÄPP = "Dra och släpp i text"
    TEXTALTERNATIV = "Textalternativ"
    ESSÄ = "Essäfråga"
    KORT_SVAR = "Kortsvarsfråga"
    UNKNOWN = "Okänd"


@dataclass
class Option:
    """An answer option for multiple choice questions."""

    text: str
    is_correct: bool = False


@dataclass
class ImageRef:
    """Reference to an extracted image."""

    path: str  # Relative path to image file
    width: int
    height: int
    image_type: str  # png, jpeg, etc.
    is_annotatable_paper: bool = False  # Full-page drawing paper

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "type": self.image_type,
            "is_paper": self.is_annotatable_paper,
        }


@dataclass
class HotspotRegion:
    """A clickable region for hotspot questions."""

    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.width, "h": self.height}

    def contains(self, px: int, py: int) -> bool:
        """Check if a point is within this region."""
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height


@dataclass
class DropdownChoice:
    """A dropdown choice for Textalternativ questions."""

    answer: str  # The selected/correct answer
    options: list[str] = field(default_factory=list)  # All available options

    def to_dict(self) -> dict:
        return {"answer": self.answer, "options": self.options}


@dataclass
class Question:
    """A parsed exam question."""

    number: int
    text: str
    question_type: str
    points: float = 0
    category: str = ""
    options: list[Option] = field(default_factory=list)
    correct_answer: str | list[str] | None = None
    answer: str | list[str] = ""
    expected_answers: int | str = 1  # Number of expected answers (e.g., 2, "2+")
    # Position information for image association
    page_num: int = -1
    y_position: float = 0.0
    # Extracted images
    images: list[ImageRef] = field(default_factory=list)
    # Hotspot answer regions (blue highlighted areas)
    hotspot_regions: list[HotspotRegion] = field(default_factory=list)
    # Dropdown choices for Textalternativ questions (DSL format)
    choices: dict[str, DropdownChoice] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert question to dictionary format."""
        d = {
            "number": self.number,
            "text": self.text,
            "type": self.question_type,
            "points": self.points,
        }
        if self.category:
            d["category"] = self.category
        if self.expected_answers != 1:
            d["expected_answers"] = self.expected_answers
        if self.options:
            d["options"] = [{"text": o.text, "is_correct": o.is_correct} for o in self.options]
        if self.choices:
            d["choices"] = {k: v.to_dict() for k, v in self.choices.items()}
        elif self.answer:
            d["answer"] = self.answer
        if self.images:
            d["images"] = [img.to_dict() for img in self.images]
        if self.hotspot_regions:
            d["hotspot_regions"] = [r.to_dict() for r in self.hotspot_regions]
        return d

    def has_answer(self) -> bool:
        """Check if this question has answer data."""
        if self.choices:
            return True
        if isinstance(self.answer, list):
            if self.answer:
                return True
        elif self.answer:
            return True
        if self.correct_answer:
            return True
        if any(o.is_correct for o in self.options):
            return True
        return False

    def has_images(self) -> bool:
        """Check if this question has associated images."""
        return len(self.images) > 0


@dataclass
class ExamMetadata:
    """Metadata for a parsed exam."""

    course_code: str = ""
    exam_title: str = ""
    date: str = ""
    is_graded: bool = False


@dataclass
class ParsedExam:
    """A fully parsed exam with all questions."""

    filename: str
    course: str
    metadata: ExamMetadata
    questions: list[Question]

    def to_dict(self) -> dict:
        """Convert exam to dictionary format."""
        return {
            "filename": self.filename,
            "course": self.course,
            "metadata": asdict(self.metadata),
            "questions": [q.to_dict() for q in self.questions],
            "total_questions": len(self.questions),
        }
