# disa-parser

A Python library for parsing DISA (Digital Examination System) exam PDFs with answer extraction.

## Overview

DISA is a digital examination system used by various educational institutions for digital exams. This library parses exam PDFs and extracts:

- Questions with their text and metadata
- Answer options for multiple choice questions
- Correct answers (when marked in the PDF)
- Points/scores
- Question categories
- **Images** associated with questions (including annotatable papers)

## Installation

```bash
pip install disa-parser
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add disa-parser
```

## Quick Start

### As a Library

```python
from disa_parser import DISAParser, parse_exam

# Simple usage
exam = parse_exam("exam.pdf", "course_name")
for question in exam.questions:
    print(f"Q{question.number}: {question.text}")
    if question.has_answer():
        print(f"  Answer: {question.answer}")

# More control with the parser class
parser = DISAParser("exam.pdf", "course_name")
exam = parser.parse()
parser.close()

# Convert to dictionary
data = exam.to_dict()
```

### As a CLI Tool

```bash
# Process a directory of exams (main workflow)
disa-parser process ./exams/              # Scan, detect & parse all DISA exams
disa-parser process ./exams/ -o output/   # Custom output directory
disa-parser process ./exams/ -w 8         # Use 8 worker processes

# Parse a single exam
disa-parser parse exam.pdf
disa-parser parse exam.pdf --limit 5      # Show first 5 questions

# Debug PDF structure
disa-parser debug blocks exam.pdf 5       # Text blocks on page 5
disa-parser debug toc exam.pdf            # Table of contents
disa-parser debug drawings exam.pdf 10    # Drawings on page 10

# Dump pages to JSON for testing
disa-parser dump exam.pdf 5 10 -o fixture.json

# Extract images from exam
disa-parser images exam.pdf -o images/
disa-parser images exam.pdf -v              # Verbose per-question breakdown
```

### Batch Processing

The `process` command is the main workflow for batch processing:

```bash
disa-parser process /path/to/exams/
```

It automatically:
- Scans directories recursively for PDF files
- Detects which files are actual DISA exams
- Skips merged/collection files (multiple exams in one PDF)
- Skips ungraded exams (`utan_svar` files)
- Parses valid exams using multiple CPU cores
- Exports questions with answers to YAML files

### Detection Functions

```python
from disa_parser import is_disa_exam, is_merged_exam, scan_directory

# Check if a PDF is a DISA exam
if is_disa_exam("exam.pdf"):
    print("This is a DISA exam!")

# Check if a PDF is a merged collection
if is_merged_exam("exam.pdf"):
    print("This is a merged file, skip it")

# Scan a directory for valid DISA exams
exams = scan_directory("/path/to/exams/")
for pdf_path in exams:
    print(f"Found: {pdf_path}")
```

### Image Extraction

Extract images from exam PDFs and associate them with questions:

```python
from disa_parser import ImageExtractor, DISAParser

# Extract all images from a PDF
extractor = ImageExtractor("exam.pdf")
images = extractor.extract_all_images()

for img in images:
    print(f"Page {img.page_num}: {img.width}x{img.height} {img.image_type}")

    # Check if it's a full-page annotatable paper
    if img.is_full_page(page_width=600, page_height=850):
        print("  This is an annotatable paper!")

    # Save the image
    img.save(f"output/image_{img.xref}.{img.image_type}")

# Find annotatable papers (full-page images for drawing)
papers = extractor.extract_annotatable_papers()
for page_num, paper in papers:
    print(f"Found annotatable paper on page {page_num}")

extractor.close()
```

Questions track their associated images:

```python
# After parsing, questions have page position info
exam = parse_exam("exam.pdf", "course")
for q in exam.questions:
    print(f"Q{q.number} on page {q.page_num} at y={q.y_position}")

    # Images are associated based on position
    for img in q.images:
        print(f"  Image: {img.path} ({img.width}x{img.height})")
        if img.is_annotatable_paper:
            print("    This is an annotatable paper!")
```

## Supported Question Types

| Code | Swedish Name | Description |
|------|-------------|-------------|
| mc1 | Flervalsfråga | Single-choice multiple choice |
| mcn | Flersvarsfråga | Multi-choice multiple choice |
| tf | Sant/Falskt | True/False |
| ess | Essäfråga | Essay |
| txt | Textområde/Textfält | Text area (labeling) |
| match | Matchning | Matching |
| hot | Hotspot | Image click |
| drag | Dra och släpp | Drag & drop |
| drop | Textalternativ | Dropdown |

## Data Models

### Question

```python
from disa_parser import Question, Option

question = Question(
    number=1,
    text="What is the capital of Sweden?",
    question_type="Flervalsfråga",
    points=1.0,
    options=[
        Option(text="Oslo", is_correct=False),
        Option(text="Stockholm", is_correct=True),
        Option(text="Helsinki", is_correct=False),
    ]
)

# Check if answer data exists
if question.has_answer():
    print("Answer found!")

# Convert to dictionary
data = question.to_dict()
```

### ParsedExam

```python
from disa_parser import ParsedExam, ExamMetadata

exam = ParsedExam(
    filename="exam.pdf",
    course="biokemi",
    metadata=ExamMetadata(
        course_code="BIO123",
        exam_title="Introduction to Biology",
        date="01.01.2024",
        is_graded=True
    ),
    questions=[...]
)
```

## Testing with Fixtures

The library includes a fixture system for testing without actual PDF files:

```python
from disa_parser import dump_pages, load_fixture, DISAParser

# Dump pages from a real PDF
fixture = dump_pages("exam.pdf", pages=[0, 5, 10])
# Save to JSON for later use
import json
Path("fixture.json").write_text(json.dumps(fixture, indent=2))

# Load fixture and use with parser
doc = load_fixture("fixture.json")
parser = DISAParser(Path("exam.pdf"), "course", fixture=doc)
result = parser.parse()
```

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/jdahlin/disa-parser
cd disa-parser

# Install with dev dependencies
uv sync --all-extras
```

### Running Tests

```bash
uv run pytest tests/ -v
```

### Project Structure

```
disa-parser/
├── src/
│   └── disa_parser/
│       ├── __init__.py    # Public API exports
│       ├── cli.py         # Command-line interface
│       ├── constants.py   # Type codes, patterns, thresholds
│       ├── fixture.py     # Test fixture support
│       ├── images.py      # Image extraction
│       ├── models.py      # Data classes
│       └── parser.py      # Main parser implementation
├── tests/
│   ├── conftest.py        # Test fixtures
│   ├── test_fixture.py    # Fixture tests
│   ├── test_images.py     # Image extraction tests
│   ├── test_models.py     # Model tests
│   └── test_parser.py     # Parser tests
├── docs/                  # Documentation
├── pyproject.toml
└── README.md
```

## Answer Detection

The parser detects correct answers through:

- **Green boxes**: RGB where r < 0.3, g > 0.4, b < 0.2 (MCQ correct markers)
- **Blue regions**: RGB where r < 0.2, g > 0.5, b > 0.8 (hotspot markers)
- **Georgia font**: Answer text in essay/text questions
- **Green text**: Color code 0x008000 (32768)
- **Checkmarks**: Unicode characters ✓ ✔ ● etc.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
