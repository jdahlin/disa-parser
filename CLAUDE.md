# CLAUDE.md - DISA Parser Instructions

## Goal
Parse DISA exam PDFs with **100% accuracy** - if one answer can be extracted from an exam, all answers should be extractable.

## Current Status (January 2025)

**Coverage: 7944/8063 questions (98.5%)**

| Type | Coverage | Missing | Notes |
|------|----------|---------|-------|
| hot | 100.0% | 0 | ✅ Complete! |
| tf | 100.0% | 0 | ✅ Complete! |
| mc1 | 99.5% | 17 | Single-choice MCQ |
| ess | 99.6% | 10 | Essays |
| mcn | 99.0% | 12 | Multi-choice MCQ |
| drop | 96.2% | 3 | Dropdowns |
| drag | 95.6% | 6 | Drag & drop |
| match | 88.3% | 11 | Matching tables |
| **txt** | **83.0%** | **60** | ⚠️ Text labeling - needs work |

**Priority focus:** txt (60 missing), match (11 missing)

## Environment & Tools

### Python Execution
- **Always use `uv run script.py`** for Python scripts
- Never use bare `python3` - dependencies won't be available
- Run commands from the `disa-parser/` directory

### Working Style
- **Don't ask questions** - just do it (yolo permission mode)
- **Validate every parser change** - run validation before AND after

## Main CLI: disa-cli.py

Unified command-line tool for all DISA parser operations:

```bash
# Validation
uv run disa-cli.py validate                    # Run full validation
uv run disa-cli.py validate --missing          # Show all missing questions
uv run disa-cli.py validate --missing --type txt  # Filter by type

# Parse single exam
uv run disa-cli.py parse path/to/exam.pdf
uv run disa-cli.py parse exam.pdf --limit 5    # Show first 5 questions

# Debug PDF structure
uv run disa-cli.py debug blocks exam.pdf 5     # Text blocks on page 5
uv run disa-cli.py debug toc exam.pdf          # TOC structure
uv run disa-cli.py debug drawings exam.pdf 10  # Drawings on page 10

# Export to YAML
uv run disa-cli.py export

# Create test fixtures
uv run disa-cli.py dump exam.pdf 5 10 -o test.json  # Specific pages
uv run disa-cli.py dump exam.pdf --all -o full.json # All pages
```

## Parser Change Workflow

**Critical: Always validate coverage before AND after changes:**

```bash
# 1. Get baseline coverage
uv run disa-cli.py validate

# 2. Make parser changes in disa.py...

# 3. Validate - coverage must increase or stay same
uv run disa-cli.py validate
```

**Rules:**
- Coverage must **increase or stay same** after changes
- If coverage **decreases**, revert the change immediately
- Use `--missing --type <type>` to debug specific question types

## Project Structure

```
disa-parser/
├── disa.py                 # Main parser module
├── disa-cli.py             # Unified CLI tool
├── disa_fixture.py         # JSON fixture serialization
├── disa_exams.csv          # All DISA exams (course + filename)
├── output_questions/       # Exported YAML (one per question)
├── scripts/                # Legacy debug scripts
├── docs/                   # Documentation
│   ├── parser-spec.md      # Technical spec for PDF parsing
│   ├── output-format.md    # Output YAML format
│   └── disa-implementation.md  # Implementation notes
└── .parser_baseline.yaml   # Validation baseline (auto-generated)

# Sibling directories (for reference):
../kandidaterna-scraper/    # Web scraper + scraped PDFs
../canvas-extractor/        # Canvas LMS integration
```

## Key Files

| File | Purpose |
|------|---------|
| `disa.py` | Main parser - all parsing logic |
| `disa-cli.py` | Unified CLI for all operations |
| `disa_fixture.py` | Serialize/deserialize PyMuPDF structures |
| `disa_exams.csv` | List of all exams (course + filename) |
| `docs/parser-spec.md` | Technical spec for PDF parsing |
| `docs/disa-implementation.md` | Implementation notes and algorithms |

## Key Concepts Learned

### Answer Detection
- **MCQ (green boxes):** RGB r < 0.3, g > 0.4, b < 0.2, match by y-position
- **Hotspots (blue regions):** RGB r < 0.2, g > 0.5, b > 0.8, fill or stroke
- **Text fields:** Georgia font or green text color (0x008000)

### TOC Parsing
- TOC spans pages 0-5
- Question types in separate column with variable x-position
- Match numbers to types by y-position (±5 pixels)

### Blacklisted Files
Merged exam collections that duplicate content:
- `YZf9yLAXGlkpSbQ9GKlt_Tentor_med_svar.pdf`
- `7I3UGkJgSQcYE18EYYMR_Tentor_med_svar.pdf`
- `LCjrBjJiquEd9Vv2c24A_Tentor_med_svar.pdf`
- `tUEMcmS1CrYLJ1LWhpqG_Tentor_med_svar_.pdf`

Exams with "utan_svar" in filename are intentionally ungraded (blank templates).

## Question Types

| Code | Swedish | Description |
|------|---------|-------------|
| mc1 | Flervalsfråga | Single-choice MCQ |
| mcn | Flersvarsfråga | Multi-choice MCQ |
| tf | Sant/Falskt | True/False |
| ess | Essä/Essäfråga | Essay |
| txt | Textområde/Textfält | Text area (labeling) |
| match | Matchning | Matching |
| hot | Hotspot | Image click |
| drag | Dra och släpp | Drag & drop |
| drop | Textalternativ | Dropdown |

## Next Steps (for continuing work)

1. **txt questions (60 missing):** Text area/labeling questions - investigate remaining answer formats
2. **match questions (11 missing):** Matching questions with table layouts - may need different parsing approach
