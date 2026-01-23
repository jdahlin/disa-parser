"""DISA Exam Parser - Main parser implementation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import fitz

from .constants import (
    CORRECT_MARKERS,
    EXPECTED_ANSWERS_PATTERN,
    FORMATS,
    GREEN_THRESHOLD,
    INCORRECT_MARKERS,
    MULTIPLE_ANSWERS_PATTERN,
    POINTS_PATTERN,
    QUESTION_TYPES,
    SWEDISH_NUMBERS,
)
from .models import DropdownChoice, ExamMetadata, HotspotRegion, Option, ParsedExam, Question, QuestionType

if TYPE_CHECKING:
    from .fixture import MockDocument


class DISAParser:
    """Parser for DISA exam PDFs.

    Extracts questions, answer options, and correct answers from DISA
    (Digital Examination System) exam PDFs.

    Args:
        pdf_path: Path to PDF file (or .json fixture file)
        course: Course identifier
        fixture: Optional pre-loaded MockDocument from fixture.load_fixture()
    """

    def __init__(
        self,
        pdf_path: Path | str,
        course: str,
        fixture: MockDocument | None = None,
    ) -> None:
        self.pdf_path = Path(pdf_path)
        self.course = course

        # Support fixture input for testing
        if fixture is not None:
            self.doc: Any = fixture
        elif str(pdf_path).endswith(".json"):
            from .fixture import load_fixture

            self.doc = load_fixture(pdf_path)
        else:
            self.doc = fitz.open(pdf_path)

        self.questions: list[Question] = []
        self.metadata = ExamMetadata()
        self.question_types: dict[int, str] = {}
        self.X_QUESTION_NUMBER = 45
        self.X_OPTION = 70

    def close(self) -> None:
        """Close the PDF document."""
        self.doc.close()

    def parse(self) -> ParsedExam:
        """Parse the PDF and return a ParsedExam object."""
        self._detect_format()
        self._parse_metadata()
        self._parse_question_summary()
        self._parse_questions()
        self._detect_graded()
        return ParsedExam(
            filename=self.pdf_path.name,
            course=self.course,
            metadata=self.metadata,
            questions=self.questions,
        )

    def _detect_format(self) -> None:
        """Detect the exam format based on first pages content."""
        text = self.doc[0].get_text()
        if len(self.doc) > 1:
            text += self.doc[1].get_text()
        if "LPG" in text and "Digital tentamen" in text:
            fmt = "LPG-digital"
        elif "TENTAMEN" in text:
            fmt = "TENTAMEN"
        else:
            fmt = "other"
        thresholds = FORMATS[fmt]
        self.X_QUESTION_NUMBER = thresholds["X_QUESTION_NUMBER"]
        self.X_OPTION = thresholds["X_OPTION"]

    def _detect_graded(self) -> None:
        """Detect if the exam has been graded (has correct answers marked)."""
        has_correct = any(
            any(o.is_correct for o in q.options) for q in self.questions if q.options
        )
        if has_correct:
            self.metadata.is_graded = True
            return
        for page_num in range(len(self.doc)):
            if self._get_green_boxes(self.doc[page_num]):
                self.metadata.is_graded = True
                return

    def _parse_metadata(self) -> None:
        """Parse exam metadata from the first page."""
        if len(self.doc) < 1:
            return
        text = self.doc[0].get_text()
        match = re.search(r"Kurskod\s+([A-Z]{2,5}\d{3})", text)
        if match:
            self.metadata.course_code = match.group(1)
        match = re.search(r"TENTAMEN\s*\n\s*(.+?)(?:\n|$)", text)
        if match:
            self.metadata.exam_title = match.group(1).strip()
        match = re.search(r"Starttid\s+(\d{2}\.\d{2}\.\d{4})", text)
        if match:
            self.metadata.date = match.group(1)

    def _parse_question_summary(self) -> None:
        """Parse the TOC table on pages 0-5 to get question types."""
        self.question_types = {}

        # First pass: collect all numbers and types with their positions
        all_numbers: list[tuple[int, int, int, int]] = []  # (page, x, y, num)
        all_types: list[tuple[int, int, int, str]] = []  # (page, x, y, type)

        for page_num in range(0, min(6, len(self.doc))):
            page = self.doc[page_num]
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        x, y = bbox[0], bbox[1]
                        text = span.get("text", "").strip()

                        # Potential question number (1-3 digits, value 1-200)
                        if re.match(r"^\d{1,3}$", text):
                            num = int(text)
                            if 1 <= num <= 200:
                                all_numbers.append((page_num, round(x), round(y), num))

                        # Question type
                        if text in QUESTION_TYPES:
                            all_types.append((page_num, round(x), round(y), text))

        # Find the type column x-position (most common x for types)
        type_x = None
        if all_types:
            type_x_positions = [x for _, x, _, _ in all_types]
            type_x = max(set(type_x_positions), key=type_x_positions.count)

        # Find the question number column x-position
        # Group numbers by x position
        numbers_by_x: dict[int, list[tuple[int, int, int]]] = {}
        for page, x, y, num in all_numbers:
            if x not in numbers_by_x:
                numbers_by_x[x] = []
            numbers_by_x[x].append((page, y, num))

        # Find the best candidate for question number column
        number_x = None
        best_score = 0

        for x, nums in numbers_by_x.items():
            # Skip if this column is at/after the type column
            if type_x is not None and x >= type_x:
                continue

            values = [n for _, _, n in nums]
            # Score: prefer columns with more variety and larger numbers
            unique_values = len(set(values))
            has_large = any(v > 10 for v in values)
            score = unique_values + (10 if has_large else 0)

            if score > best_score:
                best_score = score
                number_x = x

        # Second pass: match numbers with types by y-position
        for page_num in range(0, min(6, len(self.doc))):
            # Get numbers and types for this page
            page_numbers = [
                (y, num)
                for p, x, y, num in all_numbers
                if p == page_num and (number_x is None or abs(x - number_x) < 15)
            ]
            page_types = [
                (y, t)
                for p, x, y, t in all_types
                if p == page_num and (type_x is None or abs(x - type_x) < 20)
            ]

            # Match by y-position
            for y_num, num in page_numbers:
                for y_type, qtype in page_types:
                    if abs(y_num - y_type) < 5:
                        self.question_types[num] = qtype
                        break

        # Fallback: if position-based matching found very few, try line-based
        if len(self.question_types) < 10:
            types = []
            numbers = []
            for page_num in range(0, min(6, len(self.doc))):
                lines = self.doc[page_num].get_text().split("\n")
                for line in lines:
                    line = line.strip()
                    if line in QUESTION_TYPES:
                        types.append(line)
                    elif re.match(r"^\d{1,3}$", line):
                        num = int(line)
                        if 1 <= num <= 100:
                            numbers.append(num)
            if len(types) == len(numbers) and len(types) > 0:
                for num, qtype in zip(numbers, types):
                    if num not in self.question_types:
                        self.question_types[num] = qtype

    def _find_first_question_page(self) -> int:
        """Find the page number where questions start."""
        # Markers that indicate a question page (essay, MCQ, etc.)
        question_markers = [
            "Skriv in ditt svar",
            "Totalpoäng:",
            "Bifoga ritning",
            "Välj ett alternativ",  # MCQ marker
            "Välj ett eller flera",  # Multi-select MCQ marker
        ]
        for page_num in range(len(self.doc)):
            text = self.doc[page_num].get_text()
            if any(m in text for m in question_markers):
                if re.search(r"^\d{1,3}\s+\w", text, re.MULTILINE):
                    return page_num
        return 3 if len(self.doc) > 3 else 1

    def _parse_questions(self) -> None:
        """Parse all questions from the exam."""
        start_page = self._find_first_question_page()
        current_question: Question | None = None
        current_text_parts: list[str] = []
        current_answer_parts: list[str] = []  # Text in Georgia font (answer text)
        current_options: list[Option] = []
        current_blue_regions: list[tuple[int, int, int, int]] = []
        seen_questions: set[int] = set()

        for page_num in range(start_page, len(self.doc)):
            page = self.doc[page_num]
            blocks = self._get_sorted_blocks(page)
            page_blue_regions = self._get_blue_regions(page)

            for block in blocks:
                text = block["text"].strip()
                x_pos = block["x"]
                if not text or self._is_header_footer(text):
                    continue

                is_question_number_pos = x_pos < self.X_QUESTION_NUMBER
                is_option_pos = x_pos >= self.X_OPTION

                q_match = re.match(r"^(\d{1,3})(?:\s+(.*))?$", text)
                q_match_merged = re.match(r"^(\d{1,3})([A-Za-z].*)$", text)

                if is_question_number_pos and (q_match or q_match_merged):
                    if q_match:
                        q_num = int(q_match.group(1))
                        remaining = q_match.group(2) or ""
                    else:
                        q_num = int(q_match_merged.group(1))
                        remaining = q_match_merged.group(2) or ""

                    if 1 <= q_num <= 100 and q_num not in seen_questions:
                        if current_question:
                            self._finalize_question(
                                current_question,
                                current_text_parts,
                                current_options,
                                current_answer_parts,
                                current_blue_regions,
                            )
                            self.questions.append(current_question)

                        q_type = self.question_types.get(
                            q_num, QuestionType.UNKNOWN.value
                        )
                        seen_questions.add(q_num)
                        category = self._extract_category(remaining)

                        initial_text: list[str] = []
                        if remaining and len(remaining) > 10 and not category:
                            initial_text = [remaining]
                        elif (
                            remaining
                            and category
                            and len(remaining) > len(category) + 5
                        ):
                            after_cat = remaining[len(category) :].strip()
                            if after_cat:
                                initial_text = [after_cat]

                        current_question = Question(
                            number=q_num,
                            text="",
                            question_type=q_type,
                            category=category,
                            page_num=page_num,
                            y_position=block["y"],
                        )
                        current_text_parts = initial_text
                        current_answer_parts = []
                        current_options = []
                        current_blue_regions = page_blue_regions
                        continue

                if current_question:
                    if "Totalpoäng:" in text:
                        match = POINTS_PATTERN.search(text)
                        if match:
                            current_question.points = float(
                                match.group(1).replace(",", ".")
                            )
                    # Special handling for Textalternativ (dropdown) questions
                    elif current_question.question_type == "Textalternativ":
                        # Skip dropdown option lists (high x, starts with "(")
                        if x_pos >= 200 and text.startswith("("):
                            continue
                        # Selected dropdown answers at x ~65-67 with is_correct
                        # These are single-word selections, not statement text
                        if (
                            block.get("is_correct")
                            and 63 < x_pos < 68
                            and len(text) < 50
                            and not text.startswith("(")
                            and ")" not in text  # Not part of statement
                        ):
                            current_answer_parts.append(text)
                        elif not self._is_skippable(text):
                            current_text_parts.append(text)
                    # Special handling for Sant/Falskt compound questions
                    elif current_question.question_type == "Sant/Falskt":
                        if text in ("Sant", "Falskt"):
                            opt = Option(
                                text=text, is_correct=block.get("is_correct", False)
                            )
                            current_options.append(opt)
                        elif not self._is_skippable(text):
                            current_text_parts.append(text)
                    elif is_option_pos and self._looks_like_option(text):
                        opt = self._parse_option(text, block)
                        if opt:
                            current_options.append(opt)
                    else:
                        if not self._is_skippable(text):
                            # For Textfält/Textområde: green checkmark marks correct answer
                            txt_types = [
                                "Textfält",
                                "Textområde",
                                "Textfält i bild",
                                "Sifferfält",
                            ]
                            if (
                                block.get("is_correct")
                                and current_question.question_type in txt_types
                            ):
                                current_answer_parts.append(text)
                            # Track answer-font text separately
                            elif block.get("is_answer_font"):
                                current_answer_parts.append(text)
                            else:
                                current_text_parts.append(text)
                        if current_question.points == 0:
                            self._extract_inline_points(text, current_question)

        if current_question:
            self._finalize_question(
                current_question,
                current_text_parts,
                current_options,
                current_answer_parts,
                current_blue_regions,
            )
            self.questions.append(current_question)

        self.questions = [q for q in self.questions if q.text.strip()]

    def _get_green_boxes(self, page: Any) -> list[tuple[float, float]]:
        """Get green box positions (correct answer markers)."""
        green_boxes = []
        for path in page.get_drawings():
            fill = path.get("fill")
            rect = path.get("rect")
            if not fill or not rect:
                continue
            r, g, b = fill
            if (
                r < GREEN_THRESHOLD[0]
                and g > GREEN_THRESHOLD[1]
                and b < GREEN_THRESHOLD[2]
            ):
                green_boxes.append((rect[1], rect[3]))
        return green_boxes

    def _get_green_checkmark_centers(
        self, page: Any
    ) -> list[tuple[int, int, int]]:
        """Get center coordinates of green checkmarks for hotspot fallback.

        Returns:
            List of (x, y, radius) tuples.
        """
        centers = []
        for path in page.get_drawings():
            fill = path.get("fill")
            rect = path.get("rect")
            if not fill or not rect:
                continue
            r, g, b = fill
            if (
                r < GREEN_THRESHOLD[0]
                and g > GREEN_THRESHOLD[1]
                and b < GREEN_THRESHOLD[2]
            ):
                x1, y1, x2, y2 = rect
                w, h = x2 - x1, y2 - y1
                # Only small checkmark boxes (typical size 10-20px)
                if 5 < w < 30 and 5 < h < 30:
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    radius = int(max(w, h) / 2) + 5  # Add padding
                    centers.append((cx, cy, radius))
        return centers

    def _get_blue_regions(self, page: Any) -> list[tuple[int, int, int, int]]:
        """Get blue highlighted regions (hotspot answers).

        Returns:
            List of (x, y, w, h) tuples.
        """
        blue_regions = []
        for path in page.get_drawings():
            rect = path.get("rect")
            if not rect:
                continue

            # Check both fill and stroke (color) for blue
            fill = path.get("fill")
            stroke = path.get("color")  # stroke/outline color

            is_blue = False
            # Blue fill: R < 0.2, G > 0.5, B > 0.8
            if fill:
                r, g, b = fill
                if r < 0.2 and g > 0.5 and b > 0.8:
                    is_blue = True
            # Blue stroke (ring/circle outline): same threshold
            if stroke and not is_blue:
                r, g, b = stroke
                if r < 0.2 and g > 0.5 and b > 0.8:
                    is_blue = True

            if is_blue:
                x, y, x2, y2 = rect
                w, h = x2 - x, y2 - y
                # Filter out tiny or huge regions
                if 5 < w < 400 and 5 < h < 400:
                    blue_regions.append((int(x), int(y), int(w), int(h)))
        return blue_regions

    def _get_dropdown_boxes(self, page: Any) -> list[dict]:
        """Detect dropdown boxes on a page.

        Dropdown boxes are identified by:
        - Rounded rectangle with gray border (0.8, 0.8, 0.8)
        - White fill
        - Multiple curve items (rounded corners)

        Returns:
            List of dicts with 'rect' (as dict with x0,y0,x1,y1) and 'y_mid' keys,
            sorted by y position.
        """
        dropdowns = []
        for d in page.get_drawings():
            rect = d.get("rect")
            color = d.get("color")
            items = d.get("items", [])

            if not rect:
                continue

            # Handle both fitz.Rect objects and list/tuple formats
            if hasattr(rect, "y0"):
                # fitz.Rect object
                rect_dict = {"x0": rect.x0, "y0": rect.y0, "x1": rect.x1, "y1": rect.y1}
            elif isinstance(rect, (list, tuple)) and len(rect) >= 4:
                # List/tuple format [x0, y0, x1, y1]
                rect_dict = {"x0": rect[0], "y0": rect[1], "x1": rect[2], "y1": rect[3]}
            else:
                continue

            # Gray bordered rectangles with many curve points = dropdown boxes
            if (
                color
                and len(color) >= 3
                and abs(color[0] - 0.8) < 0.1
                and abs(color[1] - 0.8) < 0.1
                and abs(color[2] - 0.8) < 0.1
                and len(items) >= 15
            ):
                y_mid = (rect_dict["y0"] + rect_dict["y1"]) / 2
                dropdowns.append({"rect": rect_dict, "y_mid": y_mid})

        # Sort by y position
        dropdowns.sort(key=lambda x: x["y_mid"])
        return dropdowns

    def _parse_dropdown_question(self, question: Question, page: Any) -> bool:
        """Parse a Textalternativ question with dropdown boxes.

        Extracts dropdown boxes and their selected values, creates DSL format
        with ${choices1}, ${choices2}, etc. placeholders.

        Returns:
            True if dropdowns were found and parsed, False otherwise.
        """
        dropdowns = self._get_dropdown_boxes(page)
        if not dropdowns:
            return False

        # Get all text spans with position and color
        text_dict = page.get_text("dict")
        spans = []
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"]
                    # Skip page numbers like "13/25"
                    if re.match(r"^\d+/\d+$", text.strip()):
                        continue
                    spans.append(
                        {
                            "text": text,
                            "bbox": span["bbox"],
                            "color": span.get("color", 0),
                            "is_green": span.get("color", 0) == 0x008000,
                        }
                    )

        # Sort spans by y then x
        spans.sort(key=lambda s: (s["bbox"][1], s["bbox"][0]))

        # Find the question number line to determine where this question starts
        q_num = question.number
        question_start_y = 0
        for span in spans:
            text = span["text"].strip()
            if re.match(rf"^{q_num}\s*$", text) or re.match(rf"^{q_num}\s+[A-Z]", text):
                question_start_y = span["bbox"][1]
                break

        # Extract selected value from each dropdown
        choices = {}
        for i, dd in enumerate(dropdowns):
            rect = dd["rect"]
            choice_key = f"choices{i + 1}"

            # Find text inside dropdown box
            selected = ""
            for span in spans:
                sb = span["bbox"]
                if rect["x0"] < sb[0] < rect["x1"] and rect["y0"] < sb[1] < rect["y1"]:
                    selected = span["text"].strip()
                    break

            # Find options after dropdown - look for "(" followed by comma-separated list
            # The options are in parentheses, with the correct answer in green
            # Options can be on the same line (to the right) or below the dropdown
            options = []

            # Find next dropdown y position (or large gap = end of section)
            next_dd_y = 9999
            if i + 1 < len(dropdowns):
                next_dd_y = dropdowns[i + 1]["rect"]["y0"]

            # Collect text starting with "(" after this dropdown
            options_parts = []
            in_options = False
            paren_depth = 0

            for span in spans:
                sb = span["bbox"]
                text = span["text"]
                y = sb[1]
                x = sb[0]

                # Skip text before dropdown
                if y < rect["y0"] - 5:
                    continue
                # Stop at next dropdown
                if y > next_dd_y - 15:
                    break
                # Skip text inside dropdown box
                if rect["x0"] < x < rect["x1"] and rect["y0"] < y < rect["y1"]:
                    continue

                # Look for opening paren to start options
                if not in_options:
                    if "(" in text:
                        in_options = True
                        idx = text.index("(")
                        after_paren = text[idx + 1:]
                        paren_depth = 1 + after_paren.count("(") - after_paren.count(")")
                        if after_paren.strip():
                            options_parts.append(after_paren)
                        if paren_depth <= 0 and "))" in text:
                            # Closing )) means end of this options list
                            break
                else:
                    # Continue collecting until we see "))" or paren depth = 0
                    paren_depth += text.count("(") - text.count(")")
                    options_parts.append(text)
                    # Check for end of options - "))" pattern indicates end
                    if "))" in text or (paren_depth <= 0 and text.rstrip().endswith(")")):
                        break

            # Parse options from collected text
            if options_parts:
                full_text = " ".join(options_parts)
                # Remove trailing )) och, ) och, )), ) etc.
                full_text = re.sub(r"\)+\s*(och\s*)?$", "", full_text)
                # Split by comma (but not commas inside parentheses)
                # Simple approach: split by ", " followed by lowercase letter
                raw_opts = re.split(r",\s+(?=[a-zåäö])", full_text)
                # Clean up options - remove empty, very short, or duplicates
                seen = set()
                for opt in raw_opts:
                    opt = opt.strip()
                    # Remove trailing ) if unbalanced
                    while opt.count(")") > opt.count("(") and opt.endswith(")"):
                        opt = opt[:-1].strip()
                    if opt and len(opt) > 2 and opt not in seen:
                        seen.add(opt)
                        options.append(opt)

            if selected:
                choices[choice_key] = DropdownChoice(answer=selected, options=options)

        if not choices:
            return False

        # Build question text with ${choicesN} placeholders
        # Structure: main question + "label ${choices1} och ${choices2}\n\nlabel2 ${choices3}..."
        first_dd = dropdowns[0]

        # Collect main question text (before first dropdown)
        main_question_parts = []
        for span in spans:
            sb = span["bbox"]
            y = sb[1]
            if question_start_y < y < first_dd["rect"]["y0"] - 5:
                text = span["text"].strip()
                # Skip category markers like "IH 1"
                if not re.match(r"^[A-Z]{2,3}\s*\d*$", text):
                    main_question_parts.append(span["text"])

        main_question = " ".join(main_question_parts).strip()
        main_question = re.sub(r"\s+", " ", main_question)

        # Group dropdowns by vertical sections (similar y = same line)
        sections = []  # List of lists of (dropdown_idx, label)
        current_section = []
        prev_y = None

        for i, dd in enumerate(dropdowns):
            rect = dd["rect"]
            y = rect["y0"]

            # Find label text before this dropdown
            label = ""
            for span in spans:
                sb = span["bbox"]
                sy = sb[1]
                sx = sb[0]
                text = span["text"].strip()

                # Label should be on same line as dropdown, to the left
                if abs(sy - y) < 25 and sx < rect["x0"] - 5:
                    # Skip if inside previous dropdown
                    is_inside_prev = False
                    for j in range(i):
                        pr = dropdowns[j]["rect"]
                        if pr["x0"] < sx < pr["x1"] and pr["y0"] < sy < pr["y1"]:
                            is_inside_prev = True
                            break
                    if not is_inside_prev and text and not text.startswith("("):
                        label = text.strip()

            # Check if this is same section as previous (within 80px vertically)
            if prev_y is None or abs(y - prev_y) > 80:
                # New section
                if current_section:
                    sections.append(current_section)
                current_section = [(i, label)]
            else:
                # Same section
                current_section.append((i, label))

            prev_y = y

        if current_section:
            sections.append(current_section)

        # Build DSL text from sections
        dsl_lines = []
        for section in sections:
            line_parts = []
            for idx, (dd_idx, label) in enumerate(section):
                choice_key = f"choices{dd_idx + 1}"
                part = f"${{{choice_key}}}"
                if label:
                    part = f"{label} {part}"
                line_parts.append(part)

            # Join with " och " for multiple dropdowns in same section
            dsl_lines.append(" och ".join(line_parts))

        final_dsl = "\n\n".join(dsl_lines)

        question.text = main_question + "\n\n" + final_dsl if main_question else final_dsl
        question.choices = choices
        question.expected_answers = len(choices)
        question.answer = ""  # Clear answer since we have choices

        return True

    def _get_sorted_blocks(self, page: Any) -> list[dict]:
        """Get text blocks sorted by position with correctness metadata."""
        text_dict = page.get_text("dict")
        blocks = []
        green_boxes = self._get_green_boxes(page)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            bbox = block.get("bbox")
            block_text = ""
            has_correct = False
            has_incorrect = False
            is_answer_font = False

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    block_text += span_text
                    if any(m in span_text for m in CORRECT_MARKERS):
                        has_correct = True
                    if any(m in span_text for m in INCORRECT_MARKERS):
                        has_incorrect = True
                    # Georgia font indicates answer text in txt/essay questions
                    font = span.get("font", "")
                    if "Georgia" in font and span_text.strip():
                        is_answer_font = True
                    # Green text color (0x008000 = 32768) indicates correct answer
                    color = span.get("color", 0)
                    if color == 32768 and span_text.strip():  # Green text
                        has_correct = True
                        is_answer_font = True
                # Add space between lines to prevent word merging
                block_text += " "

            block_y = bbox[1]
            if any(abs(block_y - gy) < 20 for gy, _ in green_boxes):
                has_correct = True

            if block_text.strip():
                blocks.append(
                    {
                        "text": block_text,
                        "x": bbox[0],
                        "y": bbox[1],
                        "is_correct": has_correct,
                        "is_incorrect": has_incorrect,
                        "is_answer_font": is_answer_font,
                    }
                )
        return sorted(blocks, key=lambda b: (b["y"], b["x"]))

    def _is_header_footer(self, text: str) -> bool:
        """Check if text is a header or footer to skip."""
        text = text.strip()
        if re.match(r"^LPG\d+", text):
            return True
        if re.match(r"^\d+/\d+$", text):
            return True
        if "Candidate" in text or "Digital tentamen" in text:
            return True
        return False

    def _is_skippable(self, text: str) -> bool:
        """Check if text should be skipped (instructions, etc.)."""
        text = text.strip()
        if text.startswith("Ord:") or text == "Skriv in ditt svar här":
            return True
        if text.startswith("Bifoga ritning") or text.startswith(
            "Använd följande kod:"
        ):
            return True
        if re.match(r"^[\d\s]+$", text):
            return True
        return False

    def _extract_category(self, text: str) -> str:
        """Extract category from question text."""
        if not text:
            return ""
        text = text.strip()
        question_words = [
            "Vilket",
            "Vilka",
            "Vad",
            "Hur",
            "Varför",
            "När",
            "Var",
            "Beskriv",
            "Förklara",
        ]
        if any(text.startswith(w) for w in question_words):
            return ""
        code_match = re.match(r"^([A-Z]{2,4})\s*(\d*)(?:\s|$)", text)
        if code_match:
            return code_match.group(1)
        cat_match = re.match(r"^([A-Za-zÅÄÖåäö\s,]{2,25}?)\s+\d+$", text)
        if cat_match:
            return cat_match.group(1).strip()
        return ""

    def _looks_like_option(self, text: str) -> bool:
        """Check if text looks like an answer option."""
        text = text.strip()
        # Single letters A-E or digits 1-9 are valid options (image-based MCQ)
        if re.match(r"^[A-E1-9]$", text):
            return True
        # Chemical ion notation like H+, K+, Na+, Ca2+, Mg2+ (short but valid)
        if re.match(r"^[A-Za-z]{1,2}\d*[+-]$", text):
            return True
        if len(text) < 3 or len(text) > 300:
            return False
        if "Totalpoäng:" in text or "poäng:" in text.lower():
            return False
        skip_patterns = [
            "Välj ett",
            "Välj två",
            "Välj det",
            "Markera",
            "Skriv in ditt svar",
            "Skriv ditt svar",
            "Besvara följande",
            "Svara på",
            "Beskriv",
            "Namnge",
            "Förklara",
            "Redogör",
        ]
        if any(text.startswith(p) for p in skip_patterns):
            return False
        question_starts = [
            "Vilken ",
            "Vilka ",
            "Vad ",
            "Hur ",
            "Varför ",
            "När är",
            "Var ",
            "Vilket ",
        ]
        if "?" in text and len(text) > 60:
            return False
        if any(text.startswith(w) for w in question_starts) and len(text) > 60:
            return False
        if re.match(r"^[○●◯◉]\s*", text) or re.match(r"^[a-zA-Z]\)\s*", text):
            return True
        # Accept texts up to 250 chars as potential options
        if len(text) < 250:
            return True
        return False

    def _extract_inline_points(self, text: str, question: Question) -> None:
        """Extract points from inline text."""
        match = re.search(r"\((\d+(?:[.,]\d+)?)\s*p\)", text)
        if match:
            question.points = float(match.group(1).replace(",", "."))
            return
        match = re.search(r"\s(\d+(?:[.,]\d+)?)\s*p\b", text)
        if match:
            question.points = float(match.group(1).replace(",", "."))

    def _finalize_question(
        self,
        question: Question,
        text_parts: list[str],
        options: list[Option],
        answer_parts: list[str] | None = None,
        blue_regions: list[tuple[int, int, int, int]] | None = None,
    ) -> None:
        """Finalize a question by extracting answer from text."""
        answer_parts = answer_parts or []
        blue_regions = blue_regions or []

        # Special handling for Textalternativ (dropdown) questions
        if question.question_type == "Textalternativ" and question.page_num >= 0:
            page = self.doc[question.page_num]
            if self._parse_dropdown_question(question, page):
                # Successfully parsed dropdowns, done
                return

        full_text = "\n".join(text_parts)
        answer_markers = [
            "Skriv in ditt svar här",
            "Skriv ditt svar här",
            "( )Skriv in ditt svar",
        ]

        question_text = full_text
        answer_text = ""

        # Blue regions indicate hotspot answer regions
        if blue_regions and question.question_type == "Hotspot":
            coords = [f"({x},{y})" for x, y, w, h in blue_regions]
            answer_text = ", ".join(coords)
            # Store full region bounds for validation
            question.hotspot_regions = [
                HotspotRegion(x=x, y=y, width=w, height=h)
                for x, y, w, h in blue_regions
            ]

        # Georgia font text is answer text for txt/essay questions
        # Also handles Textalternativ (dropdown) selected values
        if not answer_text and answer_parts:
            font_answer_types = [
                "Textområde",
                "Textfält",
                "Textfält i bild",
                "Sifferfält",
                "Essä",
                "Essäfråga",
                "Kortsvarsfråga",
                "Hotspot",
                "Textalternativ",
            ]
            if question.question_type in font_answer_types:
                answer_text = ", ".join(answer_parts)

        word_limit_match = re.search(
            r"\(Max\s+\d+\s+ord\)\s*(.+)$", full_text, re.DOTALL | re.IGNORECASE
        )
        if (
            not answer_text
            and word_limit_match
            and len(word_limit_match.group(1).strip()) > 10
        ):
            answer_text = word_limit_match.group(1).strip()
            question_text = full_text[: word_limit_match.end()].strip()

        if not answer_text:
            for marker in answer_markers:
                if marker in full_text:
                    parts = full_text.split(marker, 1)
                    question_text = parts[0]
                    if len(parts) > 1:
                        answer_text = parts[1].strip()
                    break

        if not answer_text:
            match = re.search(r"\(\s*\)\s*(.+)$", full_text, re.DOTALL)
            if match:
                answer_text = match.group(1).strip()
                question_text = full_text[: match.start()].strip()

        if not answer_text:
            match = re.search(r"\(\d+(?:[.,]\d+)?p\)\s*(.+)$", full_text, re.DOTALL)
            if match and len(match.group(1)) > 3:
                answer_text = match.group(1).strip()
                question_text = full_text[: match.start()].strip()

        if not answer_text:
            inline_qa = re.findall(r"\?\s*([^?]+?)(?:\s+[a-d]\)|$)", full_text)
            if inline_qa and len(inline_qa) >= 2:
                answers = [a.strip() for a in inline_qa if a.strip()]
                if answers:
                    answer_text = " | ".join(answers)

        if answer_text:
            answer_text = re.sub(
                r"\s*Totalpoäng:\s*[\d.,]+\s*", "", answer_text
            ).strip()

        essay_types = ["Essä", "Essäfråga", "Kortsvarsfråga", "Textområde"]
        if question.question_type in essay_types and options and not answer_text:
            opt_texts = [o.text for o in options]
            combined = " ".join(opt_texts)
            has_numbered = re.search(r"\d+[.:]\s*\w", combined)
            has_correct_markers = any(o.is_correct for o in options)
            if has_numbered or (len(options) <= 3 and not has_correct_markers):
                answer_text = combined
                options = []

        # Types that might have inline answers
        mcq_types = ["Flervalsfråga", "Flersvarsfråga", "Okänd"]
        if (
            question.question_type in mcq_types
            and len(options) == 1
            and not answer_text
        ):
            if not options[0].is_correct:
                answer_text = options[0].text
                options = []

        # MCQ with 0 options - extract answer from text
        if (
            question.question_type in mcq_types
            and len(options) == 0
            and not answer_text
        ):
            # Pattern 1: "A. content B. content" format
            labeled_matches = re.findall(
                r"([A-Z])\.\s*(.+?)(?=\s+[A-Z]\.\s|$)", full_text + " "
            )
            if len(labeled_matches) >= 2:
                answers = [
                    m[1].strip() for m in labeled_matches if len(m[1].strip()) > 5
                ]
                if answers:
                    answer_text = " | ".join(answers)

            # Pattern 2: "a) content b) content" format
            if not answer_text:
                lowercase_matches = re.findall(
                    r"([a-z])\)\s*(.+?)(?=\s+[a-z]\)\s|$)", full_text + " "
                )
                if len(lowercase_matches) >= 2:
                    answers = [
                        m[1].strip()
                        for m in lowercase_matches
                        if len(m[1].strip()) > 5
                    ]
                    if answers:
                        answer_text = " | ".join(answers)

            # Pattern 3: Extract answer after question mark
            if not answer_text and "?" in full_text:
                parts = full_text.rsplit("?", 1)
                if len(parts) > 1 and len(parts[1].strip()) > 5:
                    potential_answer = parts[1].strip()
                    if not any(
                        skip in potential_answer.lower()
                        for skip in ["välj", "markera", "svara"]
                    ):
                        answer_text = potential_answer
                        question_text = parts[0] + "?"

        # Hotspot questions
        if question.question_type == "Hotspot" and not answer_text:
            if "?" in full_text:
                parts = full_text.split("?", 1)
                if len(parts) > 1:
                    after_q = parts[1].strip()
                    after_q = re.sub(r"\(\d+p\)", "", after_q).strip()
                    after_q = re.sub(r"Klicka på bilden.*", "", after_q).strip()
                    answer_match = re.match(r"^(\d+|[A-Za-z])(?:\s|$)", after_q)
                    if answer_match:
                        answer_text = answer_match.group(1)
                    elif 0 < len(after_q) < 50:
                        answer_text = after_q

        question.text = self._clean_question_text(question_text)
        question.expected_answers = self._extract_expected_answers(question_text)
        question.answer = answer_text
        question.options = options
        self._identify_correct_answers(question)

        # For Flersvarsfråga without explicit count, use actual correct option count
        if question.question_type == "Flersvarsfråga" and question.expected_answers == 1:
            correct_count = sum(1 for o in question.options if o.is_correct)
            if correct_count > 1:
                question.expected_answers = correct_count

    def _parse_option(self, text: str, block: dict) -> Option | None:
        """Parse a single answer option from text."""
        text = text.strip()
        # Don't strip single-letter options (A-E) or single digits (1-9)
        if not re.match(r"^[A-E1-9]$", text):
            text = re.sub(r"^[○●◯◉]\s*", "", text)
            text = re.sub(r"^[a-zA-Z]\)\s*", "", text)
            text = re.sub(r"^[a-zA-Z]\.\s*", "", text)
            # Strip orphan close-paren at start (PDF artifact)
            text = re.sub(r"^\)\s*", "", text)
        for m in CORRECT_MARKERS + INCORRECT_MARKERS:
            text = text.replace(m, "")
        text = text.strip()
        # Allow single letters/digits for image-based MCQ
        if not text:
            return None
        if len(text) < 2 and not re.match(r"^[A-E1-9]$", text):
            return None
        return Option(text=text, is_correct=block.get("is_correct", False))

    def _identify_correct_answers(self, question: Question) -> None:
        """Identify correct answers from options."""
        correct = [opt for opt in question.options if opt.is_correct]
        if correct:
            if question.question_type == QuestionType.FLERVALSFRÅGA.value:
                question.correct_answer = correct[0].text if correct else None
            else:
                question.correct_answer = [opt.text for opt in correct]

    def _clean_question_text(self, text: str) -> str:
        """Clean up question text."""
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s*Välj ett (eller flera )?alternativ:?\s*", " ", text)
        text = re.sub(r"\s*Markera det korrekta alternativet\.?\s*", " ", text)
        text = re.sub(r"\(\d+(?:[.,]\d+)?p\)", "", text)
        text = re.sub(r"\s+\d+(?:[.,]\d+)?p\b", "", text)
        text = re.sub(r"\s*Hjälp\s*", "", text)
        return text.strip()

    def _extract_expected_answers(self, text: str) -> int | str:
        """Extract expected answer count from question text.

        Detects patterns like:
        - "Välj två", "Markera tre", "Ange 2 svar"
        - "Vilka två av...", "Vilka tre påståenden..."
        - "två korrekta", "3 alternativ"
        - "Vilka påståenden" (at least 2)
        - "Välj ett eller flera" (at least 1)

        Returns:
            - 1 = single answer (default)
            - 2, 3, etc. = exactly N answers
            - "2+" = at least 2 answers
            - "1+" = at least 1 answer
        """
        # Check for specific number patterns first (e.g., "Vilka två")
        match = EXPECTED_ANSWERS_PATTERN.search(text)
        if match:
            # Find first non-None group (pattern has multiple capture groups)
            num_str = None
            for group in match.groups():
                if group:
                    num_str = group
                    break

            if num_str:
                num_str = num_str.lower()

                # "vilka påståenden" (plural) implies at least 2
                if num_str == "påståenden":
                    return "2+"

                if num_str.isdigit():
                    return int(num_str)
                result = SWEDISH_NUMBERS.get(num_str)
                if result:
                    return result

        # "Välj ett eller flera" = at least 1
        if MULTIPLE_ANSWERS_PATTERN.search(text):
            return "1+"

        return 1


def parse_exam(pdf_path: Path | str, course: str) -> ParsedExam | None:
    """Parse a single exam PDF.

    Args:
        pdf_path: Path to the PDF file
        course: Course identifier

    Returns:
        ParsedExam object or None if parsing failed
    """
    try:
        parser = DISAParser(pdf_path, course)
        result = parser.parse()
        parser.close()
        return result
    except Exception:
        return None


# DISA exam markers - text patterns that indicate a DISA exam
DISA_MARKERS = [
    "Digital tentamen",
    "LPG",  # LPG exam system
    "Totalpoäng:",
    "Skriv in ditt svar",
    "Flervalsfråga",
    "Flersvarsfråga",
    "Sant/Falskt",
    "Essäfråga",
]

# Patterns that indicate a merged/collection file
MERGED_INDICATORS = [
    "Tentor_med_svar",
    "tentor_med_svar",
    "Samling",
    "samling",
]


def is_disa_exam(pdf_path: Path | str) -> bool:
    """Check if a PDF file is a DISA exam.

    Examines the first few pages for DISA-specific markers.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        True if the file appears to be a DISA exam
    """
    try:
        doc = fitz.open(pdf_path)
        if len(doc) < 1:
            doc.close()
            return False

        # Check first 3 pages for DISA markers
        text = ""
        for page_num in range(min(3, len(doc))):
            text += doc[page_num].get_text()

        doc.close()

        # Look for DISA-specific markers
        markers_found = sum(1 for marker in DISA_MARKERS if marker in text)
        return markers_found >= 2  # Need at least 2 markers

    except Exception:
        return False


def is_merged_exam(pdf_path: Path | str) -> bool:
    """Check if a PDF is a merged/collection exam file.

    These are files containing multiple exams merged together,
    which should be skipped as they duplicate content.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        True if the file appears to be a merged collection
    """
    path = Path(pdf_path)
    filename = path.name.lower()

    # Check filename patterns
    for indicator in MERGED_INDICATORS:
        if indicator.lower() in filename:
            return True

    # Check for very large page count (merged files typically have 100+ pages)
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)

        # Also check for multiple TOC sections (indicates merged exams)
        toc_count = 0
        for page_num in range(min(10, page_count)):
            text = doc[page_num].get_text()
            # Count occurrences of TOC-like patterns
            if "Fråga" in text and "Typ" in text and "Poäng" in text:
                toc_count += 1

        doc.close()

        # Merged files often have multiple TOCs
        if toc_count >= 3:
            return True

        # Very large files are likely merged
        if page_count > 150:
            return True

    except Exception:
        pass

    return False


def is_ungraded_exam(pdf_path: Path | str) -> bool:
    """Check if a PDF is an ungraded exam (utan_svar = without answers).

    Args:
        pdf_path: Path to the PDF file

    Returns:
        True if the file is an ungraded exam template
    """
    filename = Path(pdf_path).name.lower()
    return "utan_svar" in filename


def scan_directory(
    directory: Path | str,
    recursive: bool = True,
) -> list[Path]:
    """Scan a directory for DISA exam PDFs.

    Finds all PDF files that are valid DISA exams, excluding:
    - Non-DISA PDFs
    - Merged/collection files
    - Ungraded exams (utan_svar)

    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories

    Returns:
        List of paths to valid DISA exam PDFs
    """
    from .constants import BLACKLIST

    directory = Path(directory)
    if not directory.is_dir():
        return []

    # Find all PDFs
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdf_files = list(directory.glob(pattern))

    valid_exams = []
    for pdf_path in pdf_files:
        # Skip blacklisted files
        if pdf_path.name in BLACKLIST:
            continue

        # Skip ungraded exams
        if is_ungraded_exam(pdf_path):
            continue

        # Skip merged files
        if is_merged_exam(pdf_path):
            continue

        # Check if it's a DISA exam
        if is_disa_exam(pdf_path):
            valid_exams.append(pdf_path)

    return sorted(valid_exams)
