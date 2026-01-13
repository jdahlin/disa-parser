"""DISA Parser CLI - Command-line interface."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz
import yaml

from .constants import BLACKLIST, QUESTION_TYPES, TYPE_CODES
from .parser import DISAParser


def has_answer(q: dict) -> bool:
    """Check if a question dict has answer data."""
    if q.get("answer"):
        return True
    if q.get("correct"):
        return True
    for opt in q.get("options", []):
        if opt.get("is_correct"):
            return True
    return False


def cmd_validate(args: argparse.Namespace) -> int:
    """Run parser validation across all exams."""
    csv_file = Path(args.csv or "disa_exams.csv")
    scraped_dir = Path(args.scraped_dir or "../kandidaterna-scraper/scraped_data")

    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        return 1

    results: dict[str, dict] = {}
    type_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "with_answer": 0}
    )
    total_questions = 0
    total_with_answer = 0
    problem_exams: list[tuple[str, int, int]] = []
    fully_parsed: list[str] = []
    utan_svar: list[str] = []
    missing_questions: list[dict] = []

    with open(csv_file) as f:
        rows = list(csv.DictReader(f))

    print(f"Validating {len(rows)} exams...")

    for i, row in enumerate(rows):
        course = row["course"]
        filename = row["filename"]
        pdf_path = scraped_dir / course / "files" / filename
        exam_id = f"{course[:3]}_{filename[:15]}"
        is_utan_svar = "utan_svar" in filename.lower()

        if not pdf_path.exists() or filename in BLACKLIST:
            continue

        if is_utan_svar:
            utan_svar.append(exam_id)
            continue

        try:
            parser = DISAParser(pdf_path, course)
            result = parser.parse()
            parser.close()
            exam = result.to_dict()
        except Exception as e:
            print(f"  Error parsing {exam_id}: {e}")
            continue

        exam_data: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "with_answer": 0}
        )
        for q in exam["questions"]:
            qtype = TYPE_CODES.get(q.get("type", ""), "unk")
            exam_data[qtype]["total"] += 1
            type_totals[qtype]["total"] += 1
            total_questions += 1

            if has_answer(q):
                exam_data[qtype]["with_answer"] += 1
                type_totals[qtype]["with_answer"] += 1
                total_with_answer += 1
            else:
                missing_questions.append(
                    {
                        "path": str(pdf_path.resolve()),
                        "course": course,
                        "filename": filename,
                        "q_num": q.get("number", "?"),
                        "q_type": qtype,
                        "q_type_full": q.get("type", "Unknown"),
                        "q_text": (q.get("text", "")[:80] + "...")
                        if len(q.get("text", "")) > 80
                        else q.get("text", ""),
                    }
                )

        results[exam_id] = {k: dict(v) for k, v in exam_data.items()}
        exam_total = sum(d["total"] for d in exam_data.values())
        exam_with = sum(d["with_answer"] for d in exam_data.values())

        if exam_with == exam_total:
            fully_parsed.append(exam_id)
        else:
            problem_exams.append((exam_id, exam_total, exam_with))

        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(rows)} exams...")

    # Print summary
    print("\n" + "=" * 70)
    print("PARSER VALIDATION REPORT")
    print("=" * 70)
    pct = 100 * total_with_answer / total_questions if total_questions > 0 else 0
    print(f"\nTotal: {total_with_answer}/{total_questions} questions with answers ({pct:.1f}%)")
    print(
        f"Exams: {len(fully_parsed)} fully parsed, "
        f"{len(problem_exams)} with problems, {len(utan_svar)} utan_svar"
    )

    print("\n" + "-" * 40)
    print("BY TYPE:")
    print("-" * 40)
    for qtype in sorted(type_totals.keys()):
        t = type_totals[qtype]
        pct = 100 * t["with_answer"] / t["total"] if t["total"] > 0 else 0
        missing = t["total"] - t["with_answer"]
        status = "OK" if pct == 100 else f"({missing} missing)"
        print(f"  {qtype:8} {t['with_answer']:4}/{t['total']:4} = {pct:5.1f}% {status}")

    # Print missing questions if requested
    if args.missing:
        print("\n" + "=" * 70)
        print("MISSING QUESTIONS")
        print("=" * 70)

        filtered = missing_questions
        if args.type:
            filtered = [m for m in missing_questions if m["q_type"] == args.type]
            print(f"\nFiltered by type: {args.type}")

        by_exam: dict[str, list[dict]] = defaultdict(list)
        for m in filtered:
            by_exam[m["path"]].append(m)

        print(f"\n{len(filtered)} missing questions in {len(by_exam)} exams:\n")

        for path in sorted(by_exam.keys()):
            questions = by_exam[path]
            print(f"{path}")
            for q in sorted(questions, key=lambda x: x["q_num"]):
                print(f"  Q{q['q_num']} [{q['q_type']}] {q['q_type_full']}")
                if q["q_text"]:
                    text_preview = q["q_text"].replace("\n", " ")[:70]
                    print(f'      "{text_preview}"')
            print()

    # Save baseline
    if not args.missing:
        baseline_file = Path(".parser_baseline.yaml")
        current = {
            "total_questions": total_questions,
            "total_with_answer": total_with_answer,
            "fully_parsed": len(fully_parsed),
            "problem_exams": len(problem_exams),
            "by_type": {k: dict(v) for k, v in type_totals.items()},
            "exams": results,
        }
        with open(baseline_file, "w") as f:
            yaml.dump(current, f, default_flow_style=False)
        print(f"\nBaseline saved to {baseline_file}")

    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    """Parse a single exam and show results."""
    pdf_path = Path(args.file)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        return 1

    # Detect course from path
    course = "unknown"
    known_courses = [
        "anatomi_och_histologi_1",
        "anatomi_och_histologi_2",
        "biokemi",
        "fysiologi",
        "genetik,_patologi,_pu,_farmakologi_och_konsultation",
        "infektion,_immunologi,_reumatologi_mfl",
        "klinisk_anatomi,_radiologi_och_konsultation",
        "molekylär_cellbiologi_och_utvecklingsbiologi",
    ]
    for part in pdf_path.parts:
        if part in known_courses:
            course = part
            break

    try:
        parser = DISAParser(pdf_path, course)
        result = parser.parse()
        parser.close()
        exam = result.to_dict()
    except Exception as e:
        print(f"Error parsing: {e}")
        return 1

    print(f"=== {pdf_path.name} ===")
    print(f"Total questions: {len(exam['questions'])}")

    with_answer = sum(1 for q in exam["questions"] if has_answer(q))
    print(f"With answers: {with_answer}/{len(exam['questions'])}")

    # Type breakdown
    by_type: dict[str, list[dict]] = defaultdict(list)
    for q in exam["questions"]:
        qtype = TYPE_CODES.get(q.get("type", ""), "unk")
        by_type[qtype].append(q)

    print("\nBy type:")
    for qtype, questions in sorted(by_type.items()):
        answered = sum(1 for q in questions if has_answer(q))
        print(f"  {qtype}: {answered}/{len(questions)}")

    # Show questions
    limit = args.limit or 10
    print(f"\nFirst {limit} questions:")
    for q in exam["questions"][:limit]:
        qtype = TYPE_CODES.get(q.get("type", ""), "unk")
        answered = "Y" if has_answer(q) else "N"
        print(f"\n--- Q{q['number']} [{qtype}] answered={answered} ---")
        print(f"Type: {q['type']}")
        print(f"Points: {q['points']}")
        text_preview = q["text"][:100] + "..." if len(q["text"]) > 100 else q["text"]
        print(f"Text: {text_preview}")

        if q.get("options"):
            print(f"Options ({len(q['options'])}):")
            for opt in q["options"][:5]:
                mark = "*" if opt["is_correct"] else " "
                opt_text = opt["text"][:60] + "..." if len(opt["text"]) > 60 else opt["text"]
                print(f"  [{mark}] {opt_text}")

        if q.get("answer"):
            ans_preview = q["answer"][:100] + "..." if len(q["answer"]) > 100 else q["answer"]
            print(f"Answer: {ans_preview}")

    return 0


def cmd_debug_blocks(args: argparse.Namespace) -> int:
    """Debug raw PDF text blocks on a page."""
    pdf_path = Path(args.file)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        return 1

    doc = fitz.open(pdf_path)
    if args.page >= len(doc):
        print(f"Error: Page {args.page} out of range (0-{len(doc)-1})")
        return 1

    page = doc[args.page]
    text_dict = page.get_text("dict")

    print(f"Page {args.page} of {pdf_path.name}:")
    print()

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        bbox = block.get("bbox")
        print(f"Block at x={bbox[0]:.1f} y={bbox[1]:.1f}:")

        for line in block.get("lines", []):
            line_bbox = line.get("bbox")
            print(f"  Line at x={line_bbox[0]:.1f} y={line_bbox[1]:.1f}:")
            for span in line.get("spans", []):
                span_bbox = span.get("bbox")
                text = span.get("text", "")
                font = span.get("font", "")
                color = span.get("color", 0)
                if args.verbose:
                    print(f"    x={span_bbox[0]:.1f} font={font} color={color}: '{text}'")
                else:
                    print(f"    x={span_bbox[0]:.1f}: '{text}'")
        print()

    doc.close()
    return 0


def cmd_debug_toc(args: argparse.Namespace) -> int:
    """Debug TOC structure and type detection."""
    pdf_path = Path(args.file)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        return 1

    doc = fitz.open(pdf_path)

    results: dict[str, Any] = {
        "numbers": [],
        "types": [],
        "type_x_positions": set(),
        "number_x_positions": set(),
    }

    for page_num in range(min(6, len(doc))):
        page = doc[page_num]
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    x, y = bbox[0], bbox[1]
                    text = span.get("text", "").strip()

                    if re.match(r"^\d{1,3}$", text):
                        num = int(text)
                        if 1 <= num <= 100:
                            results["numbers"].append((page_num, x, y, num))
                            results["number_x_positions"].add(round(x))

                    if text in QUESTION_TYPES:
                        results["types"].append((page_num, x, y, text))
                        results["type_x_positions"].add(round(x))

    doc.close()

    print(f"File: {pdf_path.name}")
    print(f"\nNumber X positions: {sorted(results['number_x_positions'])}")
    print(f"Type X positions: {sorted(results['type_x_positions'])}")
    print(f"\nFound {len(results['numbers'])} numbers, {len(results['types'])} types")

    print("\nNumbers (first 20):")
    for page, x, y, num in results["numbers"][:20]:
        print(f"  p{page} x={x:5.1f} y={y:5.1f}: {num}")

    print("\nTypes (first 20):")
    for page, x, y, qtype in results["types"][:20]:
        print(f"  p{page} x={x:5.1f} y={y:5.1f}: {qtype}")

    # Match by y-position
    print("\nMatched by Y-position:")
    numbers_by_y = {(page, round(y)): num for page, x, y, num in results["numbers"]}
    types_by_y = {(page, round(y)): qtype for page, x, y, qtype in results["types"]}

    matched = 0
    for key, num in sorted(numbers_by_y.items(), key=lambda x: (x[0][0], x[1])):
        page, y = key
        for dy in range(-5, 6):
            if (page, y + dy) in types_by_y:
                qtype = types_by_y[(page, y + dy)]
                print(f"  Q{num}: {qtype}")
                matched += 1
                break

    print(f"\nMatched {matched}/{len(results['numbers'])} questions")
    return 0


def cmd_debug_drawings(args: argparse.Namespace) -> int:
    """Debug PDF drawings (colors, shapes) on a page."""
    pdf_path = Path(args.file)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        return 1

    doc = fitz.open(pdf_path)
    if args.page >= len(doc):
        print(f"Error: Page {args.page} out of range (0-{len(doc)-1})")
        return 1

    page = doc[args.page]

    print(f"Page {args.page} of {pdf_path.name}:")
    print()

    # Categorize drawings by color
    green_boxes: list[dict] = []
    blue_regions: list[dict] = []
    other: list[dict] = []

    for path in page.get_drawings():
        fill = path.get("fill")
        stroke = path.get("color")
        rect = path.get("rect")

        if not rect:
            continue

        x, y, x2, y2 = rect
        w, h = x2 - x, y2 - y

        info = {
            "rect": rect,
            "size": (w, h),
            "fill": fill,
            "stroke": stroke,
        }

        # Categorize
        if fill:
            r, g, b = fill
            if r < 0.3 and g > 0.4 and b < 0.2:  # Green
                green_boxes.append(info)
            elif r < 0.2 and g > 0.5 and b > 0.8:  # Blue
                blue_regions.append(info)
            elif fill != (1, 1, 1):  # Not white
                other.append(info)

        if stroke and not fill:
            r, g, b = stroke
            if r < 0.2 and g > 0.5 and b > 0.8:  # Blue stroke
                blue_regions.append(info)

    print(f"GREEN BOXES ({len(green_boxes)}) - correct answer markers:")
    for box in green_boxes:
        r = box["rect"]
        print(f"  ({r[0]:.1f}, {r[1]:.1f}) size={box['size'][0]:.1f}x{box['size'][1]:.1f}")

    print(f"\nBLUE REGIONS ({len(blue_regions)}) - hotspot markers:")
    for box in blue_regions:
        r = box["rect"]
        fill_str = f"fill={box['fill']}" if box["fill"] else f"stroke={box['stroke']}"
        print(f"  ({r[0]:.1f}, {r[1]:.1f}) size={box['size'][0]:.1f}x{box['size'][1]:.1f} {fill_str}")

    if args.verbose and other:
        print(f"\nOTHER COLORED ({len(other)}):")
        for box in other[:20]:
            r = box["rect"]
            print(f"  ({r[0]:.1f}, {r[1]:.1f}) fill={box['fill']}")

    doc.close()
    return 0


def _check_pdf_worker(pdf_path_str: str) -> tuple[str, str | None]:
    """Worker: Check a single PDF. Returns (path, reason) or (path, None) if valid."""
    from .parser import is_disa_exam, is_merged_exam, is_ungraded_exam

    pdf_path = Path(pdf_path_str)
    try:
        if pdf_path.name in BLACKLIST:
            return (pdf_path_str, "blacklisted")
        if is_ungraded_exam(pdf_path):
            return (pdf_path_str, "ungraded")
        if is_merged_exam(pdf_path):
            return (pdf_path_str, "merged")
        if not is_disa_exam(pdf_path):
            return (pdf_path_str, "not_disa")
        return (pdf_path_str, None)  # Valid DISA exam
    except Exception as e:
        return (pdf_path_str, f"error: {e}")


def _parse_and_export_worker(args: tuple[str, str]) -> tuple[int, int, str | None]:
    """Worker: Parse exam and export to YAML. Returns (questions, exported, error)."""
    import hashlib

    import fitz

    from .images import ImageExtractor

    pdf_path_str, output_dir_str = args
    pdf_path = Path(pdf_path_str)
    output_dir = Path(output_dir_str)

    try:
        # Detect course from path
        from .constants import COURSE_CODES

        course = "unknown"
        for part in pdf_path.parts:
            if part in COURSE_CODES:
                course = part
                break

        parser = DISAParser(pdf_path, course)
        result = parser.parse()
        parser.close()

        if not result.questions:
            return (0, 0, None)

        # Generate exam ID
        course_code = COURSE_CODES.get(course, course[:3])
        date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', result.metadata.date)
        if date_match:
            yymm = date_match.group(3)[2:] + date_match.group(2)
        else:
            yymm = "0000"
        file_hash = hashlib.md5(pdf_path.name.encode()).hexdigest()[:4]
        exam_id = f"{course_code}_{yymm}_{file_hash}"

        # Extract images and associate with questions
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        extractor = ImageExtractor(pdf_path)
        all_images = extractor.extract_all_images()
        papers = extractor.extract_annotatable_papers()

        # Build question ranges for image association
        doc = fitz.open(pdf_path)
        question_images: dict[int, list] = defaultdict(list)
        question_papers: dict[int, Any] = {}

        # Map pages to questions with y-ranges
        q_ranges = []
        for i, q in enumerate(result.questions):
            y_start = q.y_position
            if i + 1 < len(result.questions):
                next_q = result.questions[i + 1]
                if next_q.page_num == q.page_num:
                    y_end = next_q.y_position
                else:
                    y_end = doc[q.page_num].rect.height
            else:
                y_end = doc[q.page_num].rect.height if q.page_num < len(doc) else 1000
            q_ranges.append((q.page_num, y_start, y_end, q.number))

        # Associate images with questions based on position
        for img in all_images:
            img_y = img.bbox[1]
            img_page = img.page_num

            # Skip tiny images (icons, bullets)
            if img.is_tiny():
                continue

            # Check if full-page (annotatable paper)
            if img_page < len(doc):
                page_rect = doc[img_page].rect
                if img.is_full_page(page_rect.width, page_rect.height):
                    # Find which question owns this page
                    for page, y_start, y_end, q_num in q_ranges:
                        if page == img_page:
                            question_papers[q_num] = img
                            break
                    continue

            # Find which question this image belongs to
            for page, y_start, y_end, q_num in q_ranges:
                if page == img_page and y_start - 30 <= img_y < y_end:
                    question_images[q_num].append(img)
                    break

        doc.close()
        extractor.close()

        exported = 0
        for q in result.questions:
            if not q.has_answer():
                continue

            qtype = TYPE_CODES.get(q.question_type, 'unk')
            yaml_filename = f"{exam_id}_q{q.number:02d}_{qtype}.yaml"
            yaml_path = output_dir / yaml_filename

            data = {
                'exam': {
                    'id': exam_id,
                    'course': course_code,
                    'date': result.metadata.date,
                    'file': pdf_path.name,
                },
                'q': {
                    'num': q.number,
                    'type': qtype,
                    'type_full': q.question_type,
                    'pts': q.points,
                    'text': q.text,
                }
            }

            if q.category:
                data['q']['cat'] = q.category
            if q.options:
                data['q']['opts'] = [o.text for o in q.options]
                correct_indices = [i for i, o in enumerate(q.options) if o.is_correct]
                if qtype == 'mc1' and correct_indices:
                    data['q']['correct'] = correct_indices[0]
                elif correct_indices:
                    data['q']['correct'] = correct_indices
            if q.answer:
                data['q']['answer'] = q.answer

            # Save images and add references
            q_images = question_images.get(q.number, [])
            q_paper = question_papers.get(q.number)
            image_refs = []

            for i, img in enumerate(q_images):
                suffix = f"_{i}" if len(q_images) > 1 else ""
                img_filename = f"{exam_id}_q{q.number:02d}_img{suffix}.{img.image_type}"
                img_path = images_dir / img_filename
                img.save(img_path)
                image_refs.append({
                    'file': f"images/{img_filename}",
                    'width': img.width,
                    'height': img.height,
                })

            if q_paper:
                paper_filename = f"{exam_id}_q{q.number:02d}_paper.{q_paper.image_type}"
                paper_path = images_dir / paper_filename
                q_paper.save(paper_path)
                image_refs.append({
                    'file': f"images/{paper_filename}",
                    'width': q_paper.width,
                    'height': q_paper.height,
                    'is_paper': True,
                })

            if image_refs:
                data['q']['images'] = image_refs

            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            exported += 1

        return (len(result.questions), exported, None)

    except Exception as e:
        return (0, 0, str(e))


def cmd_process(args: argparse.Namespace) -> int:
    """Scan directory for DISA exams, parse them, and write YAML output."""
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"Error: Not a directory: {directory}")
        return 1

    output_dir = Path(args.output or "output_questions")
    output_dir.mkdir(exist_ok=True)

    num_workers = args.workers or os.cpu_count() or 4
    recursive = not args.no_recursive

    print(f"Scanning {directory} for DISA exams...")
    print(f"  Recursive: {recursive}")
    print(f"  Workers: {num_workers}")

    # Phase 1: Find all PDFs
    pattern = "**/*.pdf" if recursive else "*.pdf"
    all_pdfs = list(directory.glob(pattern))
    print(f"  Found {len(all_pdfs)} PDF files")

    if not all_pdfs:
        print("No PDF files found.")
        return 0

    # Phase 2: Filter to DISA exams (parallel)
    print("\nDetecting DISA exams...")

    valid_exams: list[Path] = []
    skipped: dict[str, int] = defaultdict(int)

    # Convert to strings for pickling
    pdf_paths_str = [str(p) for p in all_pdfs]

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(_check_pdf_worker, p): p for p in pdf_paths_str}
        for future in as_completed(futures):
            path_str, reason = future.result()
            if reason is None:
                valid_exams.append(Path(path_str))
            else:
                skipped[reason] += 1

    print(f"  Valid DISA exams: {len(valid_exams)}")
    for reason, count in sorted(skipped.items()):
        print(f"  Skipped ({reason}): {count}")

    if not valid_exams:
        print("\nNo valid DISA exams found.")
        return 0

    # Phase 3: Parse exams and write YAML (parallel)
    print(f"\nParsing {len(valid_exams)} exams...")

    total_questions = 0
    total_exported = 0
    errors = 0
    completed = 0

    # Convert paths to strings for pickling
    output_dir_str = str(output_dir)
    work_items = [(str(pdf), output_dir_str) for pdf in valid_exams]

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(_parse_and_export_worker, item): item[0] for item in work_items}
        for future in as_completed(futures):
            completed += 1
            questions, exported, error = future.result()
            if error:
                errors += 1
                if args.verbose:
                    pdf_name = Path(futures[future]).name
                    print(f"  Error: {pdf_name}: {error}")
            else:
                total_questions += questions
                total_exported += exported

            if completed % 25 == 0:
                print(f"  Progress: {completed}/{len(valid_exams)} exams...")

    print(f"\nDone!")
    print(f"  Exams processed: {len(valid_exams)}")
    print(f"  Total questions: {total_questions}")
    print(f"  Exported with answers: {total_exported}")
    print(f"  Errors: {errors}")
    print(f"  Output: {output_dir}/")

    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    """Dump PDF pages to JSON fixture for testing."""
    import json

    from .fixture import FixtureEncoder, dump_pages

    pdf_path = Path(args.file)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        return 1

    pages = None if args.all else (args.pages or [0])
    fixture = dump_pages(pdf_path, pages)

    if args.output:
        Path(args.output).write_text(json.dumps(fixture, indent=2, cls=FixtureEncoder))
        print(f"Dumped to {args.output}")
        print(f"  Source: {fixture['source']}")
        print(f"  Pages: {len(fixture['pages'])}")
        for p in sorted(fixture["pages"].keys(), key=int):
            blocks = len(fixture["pages"][p]["text_dict"].get("blocks", []))
            drawings = len(fixture["pages"][p]["drawings"])
            print(f"    Page {p}: {blocks} blocks, {drawings} drawings")
    else:
        import json

        print(json.dumps(fixture, indent=2, cls=FixtureEncoder))

    return 0


def cmd_images(args: argparse.Namespace) -> int:
    """Extract images from DISA exam PDFs."""
    from .images import ImageExtractor
    from .models import ImageRef

    pdf_path = Path(args.file)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        return 1

    output_dir = Path(args.output or "images")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate exam ID from filename
    exam_id = pdf_path.stem[:20].replace(" ", "_")

    print(f"Extracting images from: {pdf_path.name}")

    # First parse to get question positions
    course = "unknown"
    parser = DISAParser(pdf_path, course)
    exam = parser.parse()
    parser.close()

    print(f"  Found {len(exam.questions)} questions")

    # Extract images
    extractor = ImageExtractor(pdf_path)
    all_images = extractor.extract_all_images()
    print(f"  Found {len(all_images)} images total")

    # Find annotatable papers
    papers = extractor.extract_annotatable_papers()
    print(f"  Found {len(papers)} annotatable papers")

    # Associate images with questions based on position
    doc = fitz.open(pdf_path)
    question_images: dict[int, list] = defaultdict(list)
    question_papers: dict[int, Any] = {}

    # Build question ranges: (page, y_start, y_end, q_num)
    q_ranges: list[tuple[int, float, float, int]] = []
    for i, q in enumerate(exam.questions):
        if q.page_num < 0:
            continue
        y_start = q.y_position
        # Find y_end from next question on same page, or page bottom
        y_end = doc[q.page_num].rect.height
        for j in range(i + 1, len(exam.questions)):
            next_q = exam.questions[j]
            if next_q.page_num == q.page_num:
                y_end = next_q.y_position
                break
            elif next_q.page_num > q.page_num:
                break
        q_ranges.append((q.page_num, y_start, y_end, q.number))

    # Associate images with questions
    for img in all_images:
        img_y = img.bbox[1]
        img_page = img.page_num

        # Check if it's an annotatable paper
        page_rect = doc[img_page].rect
        if img.is_full_page(page_rect.width, page_rect.height):
            # Find which question this paper belongs to
            for page, y_start, y_end, q_num in q_ranges:
                if page == img_page:
                    question_papers[q_num] = img
                    break
            continue

        # Find which question this image belongs to
        for page, y_start, y_end, q_num in q_ranges:
            if page == img_page and y_start - 30 <= img_y < y_end:
                question_images[q_num].append(img)
                break

    doc.close()

    # Save images
    total_saved = 0
    for q in exam.questions:
        q_num = q.number
        images = question_images.get(q_num, [])
        paper = question_papers.get(q_num)

        if not images and not paper:
            continue

        # Save regular images
        for i, img in enumerate(images):
            suffix = f"_{i}" if len(images) > 1 else ""
            filename = f"{exam_id}_q{q_num:02d}_img{suffix}.{img.image_type}"
            path = output_dir / filename
            img.save(path)

            # Add reference to question
            q.images.append(ImageRef(
                path=filename,
                width=img.width,
                height=img.height,
                image_type=img.image_type,
                is_annotatable_paper=False,
            ))
            total_saved += 1

        # Save annotatable paper
        if paper:
            filename = f"{exam_id}_q{q_num:02d}_paper.{paper.image_type}"
            path = output_dir / filename
            paper.save(path)

            q.images.append(ImageRef(
                path=filename,
                width=paper.width,
                height=paper.height,
                image_type=paper.image_type,
                is_annotatable_paper=True,
            ))
            total_saved += 1

    extractor.close()

    print(f"\nResults:")
    print(f"  Images saved: {total_saved}")
    print(f"  Output directory: {output_dir}/")

    # Show per-question breakdown
    if args.verbose:
        print("\nPer-question images:")
        for q in exam.questions:
            if q.images:
                imgs = [img for img in q.images if not img.is_annotatable_paper]
                papers = [img for img in q.images if img.is_annotatable_paper]
                print(f"  Q{q.number}: {len(imgs)} images, {len(papers)} papers")

    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="DISA Parser CLI - Tool for parsing DISA exam PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s process ./exams/                # Scan & parse all DISA exams
  %(prog)s process ./exams/ -o output/     # Custom output directory
  %(prog)s process ./exams/ -w 8           # Use 8 worker processes
  %(prog)s parse exam.pdf                  # Parse single file
  %(prog)s parse exam.pdf --limit 5        # Show first 5 questions
  %(prog)s images exam.pdf -o imgs/        # Extract images from exam
  %(prog)s debug blocks exam.pdf 5         # Debug blocks on page 5
  %(prog)s dump exam.pdf 5 10 -o test.json # Dump pages to JSON
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Process (main command)
    p_process = subparsers.add_parser("process", help="Scan directory, detect DISA exams, parse & export")
    p_process.add_argument("directory", help="Directory to scan for PDF files")
    p_process.add_argument("-o", "--output", help="Output directory for YAML files (default: output_questions)")
    p_process.add_argument("-w", "--workers", type=int, help="Number of worker processes (default: CPU count)")
    p_process.add_argument("--no-recursive", action="store_true", help="Don't scan subdirectories")
    p_process.add_argument("-v", "--verbose", action="store_true", help="Show detailed error messages")

    # Parse
    p_parse = subparsers.add_parser("parse", help="Parse a single exam")
    p_parse.add_argument("file", help="Path to PDF file")
    p_parse.add_argument("--limit", type=int, help="Limit questions shown")

    # Validate
    p_validate = subparsers.add_parser("validate", help="Run parser validation")
    p_validate.add_argument(
        "--missing", action="store_true", help="Print detailed list of missing questions"
    )
    p_validate.add_argument(
        "--type", metavar="TYPE", help="Filter by question type (e.g., txt, hot, mc1)"
    )
    p_validate.add_argument("--csv", help="Path to exam CSV file")
    p_validate.add_argument("--scraped-dir", help="Path to scraped data directory")

    # Debug
    p_debug = subparsers.add_parser("debug", help="Debug PDF structure")
    debug_sub = p_debug.add_subparsers(dest="debug_cmd", help="Debug command")

    p_blocks = debug_sub.add_parser("blocks", help="Debug text blocks")
    p_blocks.add_argument("file", help="Path to PDF file")
    p_blocks.add_argument("page", type=int, help="Page number (0-indexed)")
    p_blocks.add_argument("-v", "--verbose", action="store_true", help="Show font and color info")

    p_toc = debug_sub.add_parser("toc", help="Debug TOC structure")
    p_toc.add_argument("file", help="Path to PDF file")

    p_drawings = debug_sub.add_parser("drawings", help="Debug drawings/colors")
    p_drawings.add_argument("file", help="Path to PDF file")
    p_drawings.add_argument("page", type=int, help="Page number (0-indexed)")
    p_drawings.add_argument("-v", "--verbose", action="store_true", help="Show all colored drawings")

    # Dump (PDF to JSON)
    p_dump = subparsers.add_parser("dump", help="Dump PDF pages to JSON for testing")
    p_dump.add_argument("file", help="Path to PDF file")
    p_dump.add_argument("pages", nargs="*", type=int, help="Page numbers (0-indexed)")
    p_dump.add_argument("--all", action="store_true", help="Dump all pages")
    p_dump.add_argument("-o", "--output", help="Output JSON file (default: stdout)")

    # Images
    p_images = subparsers.add_parser("images", help="Extract images from DISA exam PDFs")
    p_images.add_argument("file", help="Path to PDF file")
    p_images.add_argument("-o", "--output", help="Output directory for images (default: images/)")
    p_images.add_argument("-v", "--verbose", action="store_true", help="Show per-question breakdown")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "process":
        return cmd_process(args)
    elif args.command == "parse":
        return cmd_parse(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "debug":
        if args.debug_cmd == "blocks":
            return cmd_debug_blocks(args)
        elif args.debug_cmd == "toc":
            return cmd_debug_toc(args)
        elif args.debug_cmd == "drawings":
            return cmd_debug_drawings(args)
        else:
            p_debug.print_help()
            return 1
    elif args.command == "dump":
        return cmd_dump(args)
    elif args.command == "images":
        return cmd_images(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
