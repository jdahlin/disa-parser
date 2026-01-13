"""DISA Parser - Parse DISA exam PDFs with answer extraction.

DISA (Digital Examination System) is used by various educational institutions
for digital exams. This library parses exam PDFs and extracts questions,
answer options, and correct answers.

Basic usage:
    from disa_parser import DISAParser, parse_exam

    # Parse a single exam
    exam = parse_exam("exam.pdf", "course_name")
    for question in exam.questions:
        print(f"Q{question.number}: {question.text}")
        if question.has_answer():
            print(f"  Answer: {question.answer}")

    # Or use the parser directly for more control
    parser = DISAParser("exam.pdf", "course_name")
    exam = parser.parse()
    parser.close()
"""

from .constants import (
    BLACKLIST,
    COURSE_CODES,
    QUESTION_TYPES,
    TYPE_CODES,
)
from .fixture import (
    FixtureEncoder,
    MockDocument,
    MockPage,
    dump_pages,
    load_fixture,
    save_fixture,
)
from .images import (
    ExtractedImage,
    ImageExtractor,
    QuestionImages,
    extract_images_from_exam,
)
from .models import (
    ExamMetadata,
    HotspotRegion,
    ImageRef,
    Option,
    ParsedExam,
    Question,
    QuestionType,
)
from .parser import (
    DISAParser,
    is_disa_exam,
    is_merged_exam,
    is_ungraded_exam,
    parse_exam,
    scan_directory,
)

__version__ = "0.1.0"

__all__ = [
    # Main parser
    "DISAParser",
    "parse_exam",
    # Detection & scanning
    "is_disa_exam",
    "is_merged_exam",
    "is_ungraded_exam",
    "scan_directory",
    # Image extraction
    "ImageExtractor",
    "ExtractedImage",
    "QuestionImages",
    "extract_images_from_exam",
    # Models
    "Question",
    "Option",
    "ImageRef",
    "HotspotRegion",
    "ParsedExam",
    "ExamMetadata",
    "QuestionType",
    # Constants
    "TYPE_CODES",
    "COURSE_CODES",
    "QUESTION_TYPES",
    "BLACKLIST",
    # Fixtures (for testing)
    "dump_pages",
    "save_fixture",
    "load_fixture",
    "MockDocument",
    "MockPage",
    "FixtureEncoder",
]
