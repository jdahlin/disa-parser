#!/usr/bin/env python3
"""Extract per-question fixtures from real DISA exam PDFs.

Creates JSON fixtures for each question that can be used for testing.
Naming convention: {course}-{exam_id}-{question_num:02d}.json

Usage:
    uv run scripts/extract_question_fixtures.py path/to/exam.pdf -o tests/fixtures/questions/
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz

from disa_parser import DISAParser
from disa_parser.fixture import FixtureEncoder, dump_page


def extract_exam_id(filename: str) -> str:
    """Extract exam ID from filename.

    DISA files are typically named: {id}_{description}.pdf
    E.g., CiyL1wzjXlQxVHpLMxf7_Fysiologi_delskrivning_2_VT24.pdf
    """
    # Extract the ID part (before first underscore)
    match = re.match(r"^([A-Za-z0-9]+)_", filename)
    if match:
        return match.group(1)
    # Fallback to filename stem
    return Path(filename).stem[:20]


def extract_question_fixtures(
    pdf_path: Path,
    course: str,
    output_dir: Path,
) -> list[Path]:
    """Extract per-question fixtures from an exam PDF.

    Args:
        pdf_path: Path to the exam PDF
        course: Course identifier
        output_dir: Directory to save fixtures

    Returns:
        List of paths to created fixture files
    """
    # Parse the exam to get question boundaries
    parser = DISAParser(pdf_path, course)
    exam = parser.parse()
    parser.close()

    if not exam.questions:
        print(f"No questions found in {pdf_path}")
        return []

    # Open PDF again to extract page data
    doc = fitz.open(pdf_path)
    exam_id = extract_exam_id(pdf_path.name)

    output_dir.mkdir(parents=True, exist_ok=True)
    created_files = []

    # Group questions by page for efficient extraction
    questions_by_page: dict[int, list[tuple[int, Any]]] = {}
    for q in exam.questions:
        if q.page_num not in questions_by_page:
            questions_by_page[q.page_num] = []
        questions_by_page[q.page_num].append((q.number, q))

    for question in exam.questions:
        # Collect pages for this question (current page + possibly next)
        pages_to_include = [question.page_num]

        # Find next question to determine page range
        next_q = None
        for q in exam.questions:
            if q.number == question.number + 1:
                next_q = q
                break

        # Include pages until next question
        if next_q and next_q.page_num > question.page_num:
            pages_to_include.extend(range(question.page_num + 1, next_q.page_num + 1))

        # Always include TOC pages (0-5) for question type detection
        toc_pages = list(range(min(6, len(doc))))
        pages_to_include = sorted(set(toc_pages + pages_to_include))

        pages_to_include = sorted(set(pages_to_include))

        # Build fixture
        fixture = {
            "source": pdf_path.name,
            "exam_id": exam_id,
            "course": course,
            "page_count": len(doc),
            "question": {
                "number": question.number,
                "type": question.question_type,
                "text": question.text,
                "answer": question.answer,
                "points": question.points,
                "category": question.category,
                "options": [{"text": o.text, "is_correct": o.is_correct} for o in question.options],
                "page_num": question.page_num,
                "y_position": question.y_position,
            },
            "pages": {},
        }

        for page_num in pages_to_include:
            if 0 <= page_num < len(doc):
                fixture["pages"][str(page_num)] = dump_page(doc[page_num])

        # Save fixture
        filename = f"{course}-{exam_id}-{question.number:02d}.json"
        filepath = output_dir / filename
        filepath.write_text(json.dumps(fixture, indent=2, cls=FixtureEncoder))
        created_files.append(filepath)
        print(f"  Created: {filename}")

    doc.close()
    return created_files


def main():
    parser = argparse.ArgumentParser(
        description="Extract per-question fixtures from DISA exam PDFs"
    )
    parser.add_argument("pdf_path", type=Path, help="Path to exam PDF")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("tests/fixtures/questions"),
        help="Output directory for fixtures"
    )
    parser.add_argument(
        "-c", "--course",
        help="Course name (auto-detected from parent directory if not specified)"
    )
    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"Error: {args.pdf_path} not found")
        return 1

    # Auto-detect course from parent directory name
    course = args.course
    if not course:
        # Try to get course from grandparent (scraped_data/course/files/exam.pdf)
        course = args.pdf_path.parent.parent.name
        if course == "files":
            course = args.pdf_path.parent.parent.parent.name

    print(f"Extracting fixtures from: {args.pdf_path}")
    print(f"Course: {course}")
    print(f"Output: {args.output}")

    files = extract_question_fixtures(args.pdf_path, course, args.output)
    print(f"\nCreated {len(files)} fixture files")
    return 0


if __name__ == "__main__":
    exit(main())
