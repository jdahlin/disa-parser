"""Serialize/deserialize PyMuPDF page structures for testing parser internals.

Captures the exact output of:
- page.get_text("dict")
- page.get_drawings()

Usage:
    from disa_parser.fixture import dump_pages, load_fixture

    fixture = dump_pages("exam.pdf", [0, 5, 10])
    Path("fixture.json").write_text(json.dumps(fixture, indent=2))

    # Load and use with parser
    doc = load_fixture(fixture)
    parser = DISAParser(Path("exam.pdf"), "course", fixture=doc)
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import fitz

if TYPE_CHECKING:
    from collections.abc import Sequence


class FixtureEncoder(json.JSONEncoder):
    """JSON encoder that handles PyMuPDF types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, bytes):
            return {"__bytes__": base64.b64encode(obj).decode("ascii")}
        if isinstance(obj, fitz.Rect):
            return tuple(obj)
        if isinstance(obj, fitz.Point):
            return tuple(obj)
        return super().default(obj)


def fixture_decoder(obj: dict) -> Any:
    """JSON decoder hook for PyMuPDF types."""
    if "__bytes__" in obj:
        return base64.b64decode(obj["__bytes__"])
    return obj


def dump_page(page: fitz.Page) -> dict:
    """Dump a single page's PyMuPDF structures."""
    return {
        "text_dict": page.get_text("dict"),
        "drawings": page.get_drawings(),
    }


def dump_pages(pdf_path: str | Path, pages: Sequence[int] | None = None) -> dict:
    """Dump specified pages from a PDF.

    Args:
        pdf_path: Path to PDF file
        pages: List of page numbers (0-indexed). None = all pages.

    Returns:
        Dict with metadata and page data
    """
    doc = fitz.open(pdf_path)

    if pages is None:
        pages = list(range(len(doc)))

    fixture = {
        "source": Path(pdf_path).name,
        "page_count": len(doc),
        "pages": {},
    }

    for page_num in pages:
        if 0 <= page_num < len(doc):
            fixture["pages"][str(page_num)] = dump_page(doc[page_num])

    doc.close()
    return fixture


def save_fixture(
    pdf_path: str | Path, pages: Sequence[int], output_path: str | Path
) -> dict:
    """Dump pages and save to JSON file."""
    fixture = dump_pages(pdf_path, pages)
    Path(output_path).write_text(json.dumps(fixture, indent=2, cls=FixtureEncoder))
    return fixture


class MockPage:
    """Mock PyMuPDF page loaded from fixture data."""

    def __init__(self, page_data: dict) -> None:
        self._text_dict = page_data.get("text_dict", {"blocks": []})
        self._drawings = page_data.get("drawings", [])

        # Convert drawing tuples back from lists (JSON serialization)
        for d in self._drawings:
            if "rect" in d and isinstance(d["rect"], list):
                d["rect"] = tuple(d["rect"])
            if "fill" in d and isinstance(d["fill"], list):
                d["fill"] = tuple(d["fill"])
            if "color" in d and isinstance(d["color"], list):
                d["color"] = tuple(d["color"])

    def get_text(self, mode: str = "text") -> Any:
        """Mock get_text - returns stored dict or extracts plain text."""
        if mode == "dict":
            return self._text_dict

        # Extract plain text from dict
        lines = []
        for block in self._text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                text = "".join(span.get("text", "") for span in line.get("spans", []))
                lines.append(text)
        return "\n".join(lines)

    def get_drawings(self) -> list[dict]:
        """Mock get_drawings - returns stored drawings."""
        return self._drawings


class MockDocument:
    """Mock PyMuPDF document loaded from fixture data."""

    def __init__(self, fixture: dict) -> None:
        self._fixture = fixture
        self._pages: dict[int, MockPage] = {}

        for page_num_str, page_data in fixture.get("pages", {}).items():
            self._pages[int(page_num_str)] = MockPage(page_data)

    def __len__(self) -> int:
        return self._fixture.get("page_count", 0)

    def __getitem__(self, page_num: int) -> MockPage:
        if page_num in self._pages:
            return self._pages[page_num]
        # Return empty page for pages not in fixture
        return MockPage({"text_dict": {"blocks": []}, "drawings": []})

    def close(self) -> None:
        pass


def load_fixture(fixture: dict | str | Path) -> MockDocument:
    """Load fixture and return mock document.

    Args:
        fixture: Dict, JSON string, or path to JSON file

    Returns:
        MockDocument that mimics PyMuPDF document
    """
    if isinstance(fixture, dict):
        return MockDocument(fixture)

    if isinstance(fixture, Path):
        fixture = json.loads(fixture.read_text(), object_hook=fixture_decoder)
        return MockDocument(fixture)

    # It's a string - try as file path first, then as JSON
    if isinstance(fixture, str):
        # Check if it looks like a JSON object/array (starts with { or [)
        stripped = fixture.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            fixture = json.loads(fixture, object_hook=fixture_decoder)
            return MockDocument(fixture)

        # Try as file path
        path = Path(fixture)
        if path.exists():
            fixture = json.loads(path.read_text(), object_hook=fixture_decoder)
            return MockDocument(fixture)

        # Fall back to parsing as JSON
        fixture = json.loads(fixture, object_hook=fixture_decoder)

    return MockDocument(fixture)
