# DISA Parser Implementation Guide

This document describes the implementation details of the DISA exam PDF parser, including the unified CLI tool and key algorithms discovered during development.

## Quick Start

```bash
# Validate parser coverage
uv run disa-cli.py validate

# Show missing questions by type
uv run disa-cli.py validate --missing --type txt

# Parse a single exam (PDF or XML)
uv run disa-cli.py parse path/to/exam.pdf
uv run disa-cli.py parse path/to/fixture.xml

# Debug PDF structure
uv run disa-cli.py debug blocks exam.pdf 5
uv run disa-cli.py debug toc exam.pdf
uv run disa-cli.py debug drawings exam.pdf 10

# Export to YAML
uv run disa-cli.py export

# Dump PDF pages to JSON fixture (for testing)
uv run disa-cli.py dump exam.pdf 0 5 10 -o fixture.json
uv run disa-cli.py dump exam.pdf --all -o full.json
```

---

## JSON Test Fixtures

The parser supports loading from JSON fixtures that capture PyMuPDF's internal structures exactly. This enables:
- Storing test fixtures in git without binary PDFs
- Creating minimal reproductions for debugging
- Unit testing specific parsing scenarios

### Dumping PDF to JSON

```bash
# Dump specific pages (0-indexed)
uv run disa-cli.py dump exam.pdf 0 1 5 10 -o fixture.json

# Dump all pages
uv run disa-cli.py dump exam.pdf --all -o full_exam.json
```

### Fixture Format

The fixture captures the exact output of PyMuPDF's `page.get_text("dict")` and `page.get_drawings()`:

```json
{
  "source": "exam.pdf",
  "page_count": 33,
  "pages": {
    "5": {
      "text_dict": {
        "width": 595.0,
        "height": 842.0,
        "blocks": [
          {
            "type": 0,
            "bbox": [70.0, 100.0, 500.0, 120.0],
            "lines": [
              {
                "spans": [
                  {
                    "text": "Question text here",
                    "font": "ArialMT",
                    "size": 12.0,
                    "color": 0,
                    "bbox": [70.0, 100.0, 200.0, 115.0]
                  }
                ]
              }
            ]
          }
        ]
      },
      "drawings": [
        {
          "rect": [487.0, 153.0, 505.0, 167.0],
          "fill": [0.21, 0.55, 0.08]
        }
      ]
    }
  }
}
```

### Using Fixtures in Parser

```python
from disa import DISAParser
from pathlib import Path

# Option 1: Pass JSON path directly (auto-detected by .json extension)
parser = DISAParser(Path("fixture.json"), "test_course")
result = parser.parse()

# Option 2: Load fixture first for more control
from disa_fixture import load_fixture
doc = load_fixture(Path("fixture.json"))
parser = DISAParser(Path("fixture.json"), "test_course", fixture=doc)
result = parser.parse()
```

### Creating Test Fixtures Programmatically

```python
from disa_fixture import dump_pages, save_fixture, load_fixture

# Dump specific pages
fixture = dump_pages("exam.pdf", pages=[0, 5, 10])

# Save to file
save_fixture("exam.pdf", pages=[0, 5, 10], output_path="test.json")

# Load and use
doc = load_fixture("test.json")
```

---

## CLI Reference: disa-cli.py

The unified CLI consolidates all debugging and validation tools into one script with git-style subcommands.

### Commands

#### `validate` - Run parser validation

```bash
uv run disa-cli.py validate                    # Basic validation report
uv run disa-cli.py validate --missing          # Show all missing questions with paths
uv run disa-cli.py validate --missing --type txt  # Filter by question type
```

**Output:**
- Coverage percentage by question type
- List of fully parsed vs problematic exams
- With `--missing`: Full paths and question details for debugging

#### `parse <file>` - Parse single exam

```bash
uv run disa-cli.py parse exam.pdf              # Parse and show results
uv run disa-cli.py parse exam.pdf --limit 5    # Show first 5 questions only
```

**Output:**
- Question count and answer coverage
- Type breakdown
- Individual question details with answers

#### `debug blocks <file> <page>` - Debug text blocks

```bash
uv run disa-cli.py debug blocks exam.pdf 5     # Show blocks on page 5
uv run disa-cli.py debug blocks exam.pdf 5 -v  # Include font and color info
```

**Output:**
- Raw text blocks with x/y coordinates
- Span-level detail with text content
- Useful for understanding text positioning

#### `debug toc <file>` - Debug TOC structure

```bash
uv run disa-cli.py debug toc exam.pdf
```

**Output:**
- Question numbers found (with x/y positions)
- Question types found (with x/y positions)
- Y-position matching between numbers and types
- Match success rate

#### `debug drawings <file> <page>` - Debug drawings/colors

```bash
uv run disa-cli.py debug drawings exam.pdf 10     # Show drawings on page 10
uv run disa-cli.py debug drawings exam.pdf 10 -v  # Include all colored shapes
```

**Output:**
- Green boxes (correct answer markers)
- Blue regions (hotspot answer markers)
- Other colored shapes (with -v flag)

#### `export` - Export to YAML

```bash
uv run disa-cli.py export                      # Export to output_questions/
uv run disa-cli.py export -o custom_dir/       # Export to custom directory
```

#### `dump <file> [pages...] -o <output>` - Dump PDF to JSON fixture

```bash
uv run disa-cli.py dump exam.pdf 0 5 10 -o fixture.json  # Specific pages
uv run disa-cli.py dump exam.pdf --all -o full.json      # All pages
```

**Output:**
- JSON file with exact PyMuPDF internal structures
- Summary of pages, blocks, and drawings dumped

**Use cases:**
- Create test fixtures without binary PDFs
- Exercise parser internals in tests
- Share reproducible examples

---

## Answer Detection Algorithms

### 1. MCQ Correct Answer Detection (Green Boxes)

MCQ questions (mc1, mcn, tf) use green rectangles to mark correct answers.

**Algorithm:**
```python
def _get_green_boxes(self, page) -> list[tuple]:
    green_boxes = []
    for path in page.get_drawings():
        fill = path.get("fill")
        rect = path.get("rect")
        if not fill or not rect:
            continue
        r, g, b = fill
        # Green threshold: r < 0.3, g > 0.4, b < 0.2
        if r < 0.3 and g > 0.4 and b < 0.2:
            green_boxes.append((rect[1], rect[3]))  # y1, y2
    return green_boxes
```

**Matching to options:**
- Find green box at same y-position (±20 pixels) as option text
- Mark that option as `is_correct = True`

**PDF Structure Example:**
```xml
<drawings>
  <!-- Green box marking correct option -->
  <path fill="(0.21, 0.55, 0.08)" rect="(487, 153, 505, 167)"/>
</drawings>
<blocks>
  <block y="155">
    <span>Option B - This is correct</span>
  </block>
</blocks>
```

### 2. Hotspot Answer Detection (Blue Regions)

Hotspot questions use blue shapes to mark the answer location on images.

**Algorithm:**
```python
def _get_blue_regions(self, page) -> list[tuple]:
    blue_regions = []
    for path in page.get_drawings():
        rect = path.get("rect")
        if not rect:
            continue

        fill = path.get("fill")
        stroke = path.get("color")  # stroke/outline color

        is_blue = False
        # Check fill: R < 0.2, G > 0.5, B > 0.8
        if fill:
            r, g, b = fill
            if r < 0.2 and g > 0.5 and b > 0.8:
                is_blue = True
        # Check stroke (for circle outlines)
        if stroke and not is_blue:
            r, g, b = stroke
            if r < 0.2 and g > 0.5 and b > 0.8:
                is_blue = True

        if is_blue:
            x, y, x2, y2 = rect
            w, h = x2 - x, y2 - y
            # Filter: 5x5 minimum, 400x400 maximum
            if 5 < w < 400 and 5 < h < 400:
                blue_regions.append((int(x), int(y), int(w), int(h)))
    return blue_regions
```

**Blue Region Types Discovered:**
| Type | Typical Size | Description |
|------|-------------|-------------|
| Small marker | ~20x10 px | Checkmark-sized highlight |
| Wide bar | ~60x8 px | Horizontal highlight bar |
| Circle outline | ~30x30 px | Blue ring (stroke only) |
| Large rectangle | ~100x100 px | Area selection |

**PDF Structure Example:**
```xml
<drawings>
  <!-- Blue filled rectangle -->
  <path fill="(0.05, 0.60, 0.94)" rect="(281, 193, 302, 203)"/>
  <!-- Blue stroke circle -->
  <path stroke="(0.05, 0.60, 0.94)" rect="(150, 200, 180, 230)"/>
  <!-- Green checkmark (confirmation) -->
  <path fill="(0.21, 0.55, 0.08)" rect="(288, 196, 296, 202)"/>
</drawings>
```

### 3. Text Field Answer Detection

Text field questions (txt type) use multiple indicators for correct answers.

**Detection Methods (in priority order):**

1. **Georgia Font** - Answer text uses Georgia font (questions use ArialMT)
   ```python
   font = span.get("font", "")
   if "Georgia" in font:
       is_answer_font = True
   ```

2. **Green Text Color** - Correct answers shown in green (color code 32768)
   ```python
   color = span.get("color", 0)
   if color == 32768:  # 0x008000 = green
       has_correct = True
   ```

3. **Green Checkmark** - Small green box near the answer field
   ```python
   # Same green detection as MCQ, but check proximity to text field
   ```

**PDF Structure Example:**
```xml
<blocks>
  <block>
    <span font="ArialMT">Question text here</span>
  </block>
  <block>
    <span font="Georgia" color="32768">Correct answer</span>
  </block>
</blocks>
<drawings>
  <!-- Green checkmark next to answer -->
  <path fill="(0.21, 0.55, 0.08)" rect="(500, 195, 515, 210)"/>
</drawings>
```

### 4. Essay Answer Detection

Essay questions extract answers using text markers.

**Answer Markers (priority order):**
1. `Skriv in ditt svar här` - Text after this marker
2. `( )` - Empty parentheses followed by answer
3. `(Xp)` - Point marker followed by answer
4. `(Max N ord)` - Word limit marker followed by answer

**Algorithm:**
```python
markers = ['Skriv in ditt svar här', 'Skriv ditt svar här']
for marker in markers:
    if marker in full_text:
        parts = full_text.split(marker, 1)
        question_text = parts[0]
        answer_text = parts[1].strip() if len(parts) > 1 else ""
        break
```

---

## TOC Parsing Algorithm

The Table of Contents (pages 0-5) maps question numbers to types.

**Key Discovery:** Question types appear in a separate column with varying x-positions depending on exam format.

**Algorithm:**
1. Scan pages 0-5 for question numbers (pattern: `^\d{1,3}$`)
2. Scan same pages for question types (from known type list)
3. Record x-position of each to detect columns
4. Match numbers to types by y-position (±5 pixels tolerance)

**Format Detection:**
| Format | Number X | Type X | Prevalence |
|--------|----------|--------|------------|
| TENTAMEN | ~33 | ~326 | 86% |
| LPG-digital | ~33 | ~265 | 9% |
| Other | varies | varies | 5% |

---

## Color Reference

| Color | RGB Values | Purpose |
|-------|------------|---------|
| Green (fill) | (0.21, 0.55, 0.08) | Correct answer marker |
| Green (text) | color=32768 (0x008000) | Correct text highlight |
| Blue (fill) | (0.05, 0.60, 0.94) | Hotspot region marker |
| Blue (stroke) | (0.05, 0.60, 0.94) | Hotspot circle outline |
| White | (1.0, 1.0, 1.0) | Background (ignore) |

**Detection Thresholds:**
```python
# Green: r < 0.3, g > 0.4, b < 0.2
# Blue:  r < 0.2, g > 0.5, b > 0.8
```

---

## Current Coverage (January 2025)

| Type | Coverage | Missing | Notes |
|------|----------|---------|-------|
| hot | 100% | 0 | Blue region detection |
| tf | 100% | 0 | Green box detection |
| mc1 | 99.5% | 17 | Green box detection |
| ess | 99.6% | 10 | Text marker detection |
| mcn | 98.9% | 14 | Green box detection |
| drop | 96.5% | 3 | |
| drag | 95.8% | 6 | |
| match | 88.4% | 11 | Table layout parsing |
| txt | 83.1% | 61 | Font/color detection |

**Total: 98.5%** (8127/8250 questions)

---

## File Structure

```
kandidaterna/
├── disa.py              # Main parser module
├── disa-cli.py          # Unified CLI tool (this doc)
├── disa_exams.csv       # List of all exams
├── scraped_data/        # PDF files by course
├── output_questions/    # Exported YAML files
├── scripts/             # Legacy debug scripts
│   ├── validate_parser.py   # (superseded by disa-cli.py validate)
│   ├── debug_blocks.py      # (superseded by disa-cli.py debug blocks)
│   ├── debug_toc.py         # (superseded by disa-cli.py debug toc)
│   └── ...
├── CLAUDE.md            # Project instructions
├── DISA_PARSER_SPEC.md  # Technical specification
└── disa-implementation.md  # This file
```

---

## Debugging Workflow

### When a question type has low coverage:

1. **Find missing questions:**
   ```bash
   uv run disa-cli.py validate --missing --type <type>
   ```

2. **Pick an example exam and inspect:**
   ```bash
   uv run disa-cli.py parse path/to/exam.pdf
   ```

3. **Find the question's page and debug:**
   ```bash
   uv run disa-cli.py debug blocks exam.pdf <page>
   uv run disa-cli.py debug drawings exam.pdf <page>
   ```

4. **Look for patterns:**
   - New color markers?
   - Different font usage?
   - Different text structure?

5. **Update disa.py with new detection logic**

6. **Validate no regressions:**
   ```bash
   uv run disa-cli.py validate
   ```

---

## Legacy Scripts (in scripts/)

These scripts are superseded by `disa-cli.py` but kept for reference:

| Script | Replacement |
|--------|-------------|
| validate_parser.py | `disa-cli.py validate` |
| debug_blocks.py | `disa-cli.py debug blocks` |
| debug_toc.py | `disa-cli.py debug toc` |
| check_parse.py | `disa-cli.py parse` |
| export_questions.py | `disa-cli.py export` |

Temporary debug scripts in `/tmp/` can be deleted - their functionality is now in `disa-cli.py debug`.
