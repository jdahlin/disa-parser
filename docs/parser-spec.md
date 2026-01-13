# DISA Exam PDF Parser Specification

## Overview

Parser for DISA (Digital Examination System) exam PDFs from Göteborgs Universitet. Extracts questions, options, correct answers, and metadata for flashcard creation.

**Current Status:** 97.39% coverage (7864/8075 questions with answers)

## PDF Library

Uses PyMuPDF (fitz) for PDF parsing:
```python
import fitz  # pip install pymupdf
doc = fitz.open("exam.pdf")
```

## PDF Formats

Two main formats detected from pages 0-1:

| Format | Detection | Thresholds | Prevalence |
|--------|-----------|------------|------------|
| `TENTAMEN` | Contains "TENTAMEN" | X_QUESTION_NUMBER=45, X_OPTION=70 | 86% |
| `LPG-digital` | Contains "LPG" AND "Digital tentamen" | X_QUESTION_NUMBER=42, X_OPTION=62 | 9% |
| `other` | Neither | Same as TENTAMEN | 5% |

```python
def detect_format(doc):
    text = doc[0].get_text()
    if len(doc) > 1:
        text += doc[1].get_text()
    if 'LPG' in text and 'Digital tentamen' in text:
        return 'LPG-digital'
    elif 'TENTAMEN' in text:
        return 'TENTAMEN'
    return 'other'
```

## Document Structure

| Page | Content |
|------|---------|
| 0 | Cover page: course code, dates, candidate info |
| 0-5 | TOC: question number → type mapping |
| 3+ | Questions with options and answers |

---

## Phase 1: Metadata Extraction (Page 0)

Extract from cover page text:

```python
# Course code: "Kurskod LPG001"
match = re.search(r'Kurskod\s+([A-Z]{2,5}\d{3})', text)
course_code = match.group(1) if match else ""

# Exam date: "Starttid 17.10.2023 11:00"
match = re.search(r'Starttid\s+(\d{2}\.\d{2}\.\d{4})', text)
date = match.group(1) if match else ""
```

---

## Phase 2: TOC Parsing (Pages 0-5)

The TOC maps question numbers to question types. It's rendered as a **table with separate text spans per column**.

### TOC Structure

Each TOC row has these columns at different x-positions:
- Question number (x varies: 39-104)
- Question title
- Status (Rätt/Fel)
- Score (1/1, 2/2)
- Question type (x varies: 281-483)

### Complete TOC Algorithm

```python
def parse_toc(doc):
    """Parse TOC to get question_number -> question_type mapping."""
    question_types = {}

    # First pass: collect all numbers and types with positions
    all_numbers = []  # (page, x, y, num)
    all_types = []    # (page, x, y, type)

    QUESTION_TYPES = [
        'Flervalsfråga', 'Flersvarsfråga', 'Sant/Falskt', 'Essäfråga', 'Essä',
        'Kortsvarsfråga', 'Matchning', 'Textområde', 'Textfält', 'Textfält i bild',
        'Sifferfält', 'Hotspot', 'Dra och släpp i text', 'Dra och släpp',
        'Dra och släpp i bild', 'Dra och släpp text', 'Textalternativ', 'Sammansatt'
    ]

    for page_num in range(0, min(6, len(doc))):
        page = doc[page_num]
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Skip non-text blocks
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    x, y = round(bbox[0]), round(bbox[1])
                    text = span.get("text", "").strip()

                    # Collect potential question numbers (1-3 digits, 1-200)
                    if re.match(r'^\d{1,3}$', text):
                        num = int(text)
                        if 1 <= num <= 200:
                            all_numbers.append((page_num, x, y, num))

                    # Collect question types
                    if text in QUESTION_TYPES:
                        all_types.append((page_num, x, y, text))

    # Find type column x-position (most common x for types)
    type_x = None
    if all_types:
        type_x_positions = [x for _, x, _, _ in all_types]
        type_x = max(set(type_x_positions), key=type_x_positions.count)

    # Find number column x-position (left of types, has sequential numbers)
    numbers_by_x = {}
    for page, x, y, num in all_numbers:
        if x not in numbers_by_x:
            numbers_by_x[x] = []
        numbers_by_x[x].append((page, y, num))

    number_x = None
    best_score = 0
    for x, nums in numbers_by_x.items():
        # Skip columns at/after type column
        if type_x is not None and x >= type_x:
            continue
        values = [n for _, _, n in nums]
        unique_values = len(set(values))
        has_large = any(v > 10 for v in values)
        score = unique_values + (10 if has_large else 0)
        if score > best_score:
            best_score = score
            number_x = x

    # Match numbers to types by y-position (within 5 pixels)
    for page_num in range(0, min(6, len(doc))):
        page_numbers = [(y, num) for p, x, y, num in all_numbers
                       if p == page_num and (number_x is None or abs(x - number_x) < 15)]
        page_types = [(y, t) for p, x, y, t in all_types
                     if p == page_num and (type_x is None or abs(x - type_x) < 20)]

        for y_num, num in page_numbers:
            for y_type, qtype in page_types:
                if abs(y_num - y_type) < 5:
                    question_types[num] = qtype
                    break

    return question_types
```

### TOC Test Data (XML)

```xml
<!-- TOC from TENTAMEN format exam (typical x positions) -->
<toc_page page="1">
  <row y="150">
    <span x="39" text="1"/>
    <span x="104" text="Rörelseapparaten"/>
    <span x="200" text="Rätt"/>
    <span x="250" text="1/1"/>
    <span x="350" text="Flervalsfråga"/>
  </row>
  <row y="165">
    <span x="39" text="2"/>
    <span x="104" text="Rörelseapparaten"/>
    <span x="200" text="Fel"/>
    <span x="250" text="0/1"/>
    <span x="350" text="Flersvarsfråga"/>
  </row>
  <row y="180">
    <span x="39" text="3"/>
    <span x="104" text="Histologi"/>
    <span x="200" text="Rätt"/>
    <span x="250" text="2/2"/>
    <span x="350" text="Essäfråga"/>
  </row>
</toc_page>

<!-- TOC from exam with non-standard number column (x=104) -->
<toc_page page="2" format="biokemi_special">
  <row y="200">
    <span x="104" text="1"/>  <!-- Number column shifted right! -->
    <span x="180" text="Metabolism"/>
    <span x="350" text="Rätt"/>
    <span x="400" text="1/1"/>
    <span x="480" text="Flervalsfråga"/>  <!-- Type column also shifted -->
  </row>
  <row y="215">
    <span x="104" text="2"/>
    <span x="180" text="Metabolism"/>
    <span x="350" text="Fel"/>
    <span x="400" text="0/2"/>
    <span x="480" text="Sant/Falskt"/>
  </row>
</toc_page>

<!-- Expected parsing result -->
<expected>
  <mapping num="1" type="Flervalsfråga"/>
  <mapping num="2" type="Flersvarsfråga"/>
  <mapping num="3" type="Essäfråga"/>
</expected>
```

### Type Code Mapping

```python
TYPE_CODES = {
    'Flervalsfråga': 'mc1',      # Single-choice MCQ
    'Flersvarsfråga': 'mcn',     # Multi-choice MCQ
    'Sant/Falskt': 'tf',         # True/False
    'Essäfråga': 'ess',          # Essay
    'Essä': 'ess',               # Essay (variant)
    'Kortsvarsfråga': 'short',   # Short answer
    'Matchning': 'match',        # Matching
    'Hotspot': 'hot',            # Image click
    'Dra och släpp i text': 'drag',   # Drag & drop
    'Dra och släpp': 'drag',
    'Dra och släpp i bild': 'drag',
    'Dra och släpp text': 'drag',
    'Textalternativ': 'drop',    # Dropdown
    'Textområde': 'txt',         # Text area
    'Textfält': 'txt',
    'Textfält i bild': 'txt',
    'Sifferfält': 'txt',
    'Sammansatt': 'ess',         # Composite → essay
    'Okänd': 'unk',              # Unknown
}
```

---

## Phase 3: Question Parsing

### Find First Question Page

```python
def find_first_question_page(doc):
    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        # Questions have these markers
        if any(m in text for m in ['Skriv in ditt svar', 'Totalpoäng:', 'Bifoga ritning']):
            # And a question number pattern
            if re.search(r'^\d{1,3}\s+\w', text, re.MULTILINE):
                return page_num
    return 3 if len(doc) > 3 else 1
```

### Block Classification by X-Position

**This is the core parsing logic.** Classification is based on x-position, NOT content regex.

```python
X_QUESTION_NUMBER = 45  # or 42 for LPG-digital
X_OPTION = 70           # or 62 for LPG-digital

for block in sorted_blocks:
    x = block['x']
    text = block['text']

    if x < X_QUESTION_NUMBER:
        # QUESTION NUMBER ZONE: "1 Category" or just "1"
        start_new_question(text)
    elif x >= X_OPTION and looks_like_option(text):
        # OPTION ZONE: MCQ options
        add_option(text, block['is_correct'])
    else:
        # QUESTION TEXT ZONE: question body
        add_question_text(text)
```

### Question Number Patterns

```python
# Pattern 1: "1 Category text" or "1 Category 3"
q_match = re.match(r'^(\d{1,3})(?:\s+(.*))?$', text)
# Pattern 2: "1Text..." (merged, no space)
q_match_merged = re.match(r'^(\d{1,3})([A-Za-z].*)$', text)
```

### Question Test Data (XML)

```xml
<!-- Standard MCQ question (Flervalsfråga) -->
<page num="5">
  <!-- Question number at x=39 (left zone) -->
  <block x="39" y="100" text="1 Rörelseapparaten"/>

  <!-- Question text at x=56 (middle zone) -->
  <block x="56" y="115" text="Vilken muskel är primär flexor av armbågen?"/>

  <!-- Options at x=80 (right zone) with green box markers -->
  <block x="80" y="140" text="M. biceps brachii" green_box_y="140"/>
  <block x="80" y="160" text="M. triceps brachii"/>
  <block x="80" y="180" text="M. brachialis"/>
  <block x="80" y="200" text="M. pronator teres"/>

  <!-- Points at far right -->
  <block x="470" y="220" text="Totalpoäng: 1"/>
</page>

<expected>
  <question num="1" type="Flervalsfråga" category="Rörelseapparaten" points="1">
    <text>Vilken muskel är primär flexor av armbågen?</text>
    <options>
      <option text="M. biceps brachii" correct="true"/>
      <option text="M. triceps brachii" correct="false"/>
      <option text="M. brachialis" correct="false"/>
      <option text="M. pronator teres" correct="false"/>
    </options>
  </question>
</expected>
```

```xml
<!-- Image-based MCQ with single-letter options -->
<page num="35">
  <block x="39" y="100" text="60"/>
  <block x="56" y="115" text="Vilken siffra markerar musculus longissimus?"/>

  <!-- Single letters are valid options! -->
  <block x="80" y="140" text="A"/>
  <block x="80" y="155" text="B" green_box_y="155"/>  <!-- Correct -->
  <block x="80" y="170" text="C"/>
  <block x="80" y="185" text="D"/>
  <block x="80" y="200" text="E"/>
</page>

<expected>
  <question num="60" type="Flervalsfråga">
    <text>Vilken siffra markerar musculus longissimus?</text>
    <options>
      <option text="A" correct="false"/>
      <option text="B" correct="true"/>
      <option text="C" correct="false"/>
      <option text="D" correct="false"/>
      <option text="E" correct="false"/>
    </options>
  </question>
</expected>
```

```xml
<!-- Essay question with answer after marker -->
<page num="10">
  <block x="39" y="100" text="5 Histologi"/>
  <block x="56" y="115" text="Beskriv strukturen hos en muskelfibrill. (2p)"/>
  <block x="56" y="140" text="Skriv in ditt svar här"/>
  <block x="56" y="160" text="Myofibriller består av sarkomerer med aktin och myosin filament..."/>
</page>

<expected>
  <question num="5" type="Essäfråga" category="Histologi" points="2">
    <text>Beskriv strukturen hos en muskelfibrill.</text>
    <answer>Myofibriller består av sarkomerer med aktin och myosin filament...</answer>
  </question>
</expected>
```

---

## Phase 4: Option Detection

### Option Recognition Algorithm

```python
def looks_like_option(text):
    text = text.strip()

    # ACCEPT: Single letters A-E or digits 1-9 (image-based MCQ)
    if re.match(r'^[A-E1-9]$', text):
        return True

    # REJECT: Too short or too long
    if len(text) < 3 or len(text) > 300:
        return False

    # REJECT: Point markers
    if 'Totalpoäng:' in text or 'poäng:' in text.lower():
        return False

    # REJECT: Instructions
    skip_patterns = [
        'Välj ett', 'Välj två', 'Välj det', 'Markera',
        'Skriv in ditt svar', 'Skriv ditt svar',
        'Besvara följande', 'Svara på', 'Beskriv',
        'Namnge', 'Förklara', 'Redogör'
    ]
    if any(text.startswith(p) for p in skip_patterns):
        return False

    # REJECT: Questions (has ? and is long)
    if '?' in text and len(text) > 60:
        return False

    question_starts = ['Vilken ', 'Vilka ', 'Vad ', 'Hur ', 'Varför ', 'När är', 'Var ', 'Vilket ']
    if any(text.startswith(w) for w in question_starts) and len(text) > 60:
        return False

    # ACCEPT: Bullet markers
    if re.match(r'^[○●◯◉]\s*', text) or re.match(r'^[a-zA-Z]\)\s*', text):
        return True

    # ACCEPT: Reasonable length text (up to 250 chars)
    if len(text) < 250:
        return True

    return False
```

### Option Parsing

```python
def parse_option(text, is_correct):
    text = text.strip()

    # PRESERVE single letters (A-E) and digits (1-9)
    if not re.match(r'^[A-E1-9]$', text):
        # Strip bullet markers for normal options
        text = re.sub(r'^[○●◯◉]\s*', '', text)
        text = re.sub(r'^[a-zA-Z]\)\s*', '', text)
        text = re.sub(r'^[a-zA-Z]\.\s*', '', text)

    # Remove check markers
    for marker in ['✓', '✔', '●', '✗', '✘', '○']:
        text = text.replace(marker, '')

    text = text.strip()

    # Reject empty or too short (but allow single letters/digits)
    if not text:
        return None
    if len(text) < 2 and not re.match(r'^[A-E1-9]$', text):
        return None

    return Option(text=text, is_correct=is_correct)
```

---

## Phase 5: Green Box Detection (Correct Answers)

Green filled rectangles mark correct MCQ answers. Uses `page.get_drawings()` from PyMuPDF.

### Green Box Algorithm

```python
GREEN_THRESHOLD = (0.3, 0.4, 0.2)  # (max_r, min_g, max_b)

def get_green_boxes(page):
    """Get y-positions of green checkbox markers."""
    green_boxes = []
    for path in page.get_drawings():
        fill = path.get("fill")
        rect = path.get("rect")
        if not fill or not rect:
            continue
        r, g, b = fill
        # Green: R < 0.3, G > 0.4, B < 0.2
        # Actual observed: RGB(0.21, 0.55, 0.08)
        if r < GREEN_THRESHOLD[0] and g > GREEN_THRESHOLD[1] and b < GREEN_THRESHOLD[2]:
            green_boxes.append((rect[1], rect[3]))  # (y_top, y_bottom)
    return green_boxes

def is_option_correct(block_y, green_boxes, tolerance=20):
    """Check if an option has a green box nearby."""
    return any(abs(block_y - gy) < tolerance for gy, _ in green_boxes)
```

### Green Box Test Data (XML)

```xml
<!-- Page with MCQ options and green box markers -->
<page num="5">
  <drawings>
    <!-- Green box at y=155 marks option B as correct -->
    <path fill="(0.21, 0.55, 0.08)" rect="(487, 153, 505, 167)"/>
    <!-- Blue box indicates student selection (may be wrong) -->
    <path fill="(0.73, 0.85, 0.94)" rect="(75, 138, 500, 152)"/>
  </drawings>

  <blocks>
    <block x="80" y="140" text="Option A"/>
    <block x="80" y="155" text="Option B"/>  <!-- y=155 matches green box -->
    <block x="80" y="170" text="Option C"/>
  </blocks>
</page>

<expected>
  <option text="Option A" correct="false"/>
  <option text="Option B" correct="true"/>   <!-- Green box within 20px of y=155 -->
  <option text="Option C" correct="false"/>
</expected>
```

### Color Reference

| Color | RGB | Meaning |
|-------|-----|---------|
| Green | (0.21, 0.55, 0.08) | Correct answer marker |
| Blue | (0.73, 0.85, 0.94) | Student's selection |
| None | - | Unselected option |

**Important:** Blue WITHOUT green = wrong answer. Only use green for correctness.

---

## Phase 6: Answer Extraction (Non-MCQ)

For essay, text area, and hotspot questions, answers appear after specific markers.

### Answer Markers (Priority Order)

1. `Skriv in ditt svar här` - Text after this is the answer
2. `( )` - Empty parens followed by answer text
3. `(Xp)` - Point marker followed by answer
4. `(Max N ord)` - Word limit followed by answer

### Answer Extraction Algorithm

```python
def extract_answer(full_text, question_type):
    answer_markers = ['Skriv in ditt svar här', 'Skriv ditt svar här', '( )Skriv in ditt svar']

    question_text = full_text
    answer_text = ""

    # Pattern 1: "(Max N ord)" followed by answer
    word_limit_match = re.search(r'\(Max\s+\d+\s+ord\)\s*(.+)$', full_text, re.DOTALL | re.IGNORECASE)
    if word_limit_match and len(word_limit_match.group(1).strip()) > 10:
        answer_text = word_limit_match.group(1).strip()
        question_text = full_text[:word_limit_match.end()].strip()

    # Pattern 2: Explicit marker
    if not answer_text:
        for marker in answer_markers:
            if marker in full_text:
                parts = full_text.split(marker, 1)
                question_text = parts[0]
                if len(parts) > 1:
                    answer_text = parts[1].strip()
                break

    # Pattern 3: "( )" followed by answer
    if not answer_text:
        match = re.search(r'\(\s*\)\s*(.+)$', full_text, re.DOTALL)
        if match:
            answer_text = match.group(1).strip()
            question_text = full_text[:match.start()].strip()

    # Pattern 4: "(Xp)" followed by answer
    if not answer_text:
        match = re.search(r'\(\d+(?:[.,]\d+)?p\)\s*(.+)$', full_text, re.DOTALL)
        if match and len(match.group(1)) > 3:
            answer_text = match.group(1).strip()
            question_text = full_text[:match.start()].strip()

    # Clean up: remove trailing point markers
    if answer_text:
        answer_text = re.sub(r'\s*Totalpoäng:\s*[\d.,]+\s*', '', answer_text).strip()

    return question_text, answer_text
```

### Essay Answer Test Data (XML)

```xml
<!-- Essay with answer after marker -->
<question_text>
Beskriv kärlförsörjningen till hjärnan. (2p)
Skriv in ditt svar här
Hjärnan försörjs primärt av carotis interna och arteria vertebralis som bildar circulus arteriosus...
Totalpoäng: 2
</question_text>

<expected>
  <question_part>Beskriv kärlförsörjningen till hjärnan.</question_part>
  <answer>Hjärnan försörjs primärt av carotis interna och arteria vertebralis som bildar circulus arteriosus...</answer>
  <points>2</points>
</expected>
```

```xml
<!-- Hotspot with number answer -->
<question_text>
Vilken siffra markerar nucleus caudatus? Klicka på bilden för att svara. (1p)
3
</question_text>

<expected>
  <question_part>Vilken siffra markerar nucleus caudatus? Klicka på bilden för att svara.</question_part>
  <answer>3</answer>
  <points>1</points>
</expected>
```

---

## Phase 7: Block Sorting and Processing

### Get Sorted Blocks from Page

```python
def get_sorted_blocks(page):
    """Extract text blocks sorted by reading order (top-to-bottom, left-to-right)."""
    text_dict = page.get_text("dict")
    green_boxes = get_green_boxes(page)
    blocks = []

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:  # Skip non-text (images)
            continue

        bbox = block.get("bbox")
        block_text = ""
        has_correct = False
        has_incorrect = False

        # Extract text from spans
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                block_text += span_text

                # Check for unicode markers
                if any(m in span_text for m in ['✓', '✔', '●']):
                    has_correct = True
                if any(m in span_text for m in ['✗', '✘', '○']):
                    has_incorrect = True

        # Check for nearby green box
        block_y = bbox[1]
        if any(abs(block_y - gy) < 20 for gy, _ in green_boxes):
            has_correct = True

        if block_text.strip():
            blocks.append({
                'text': block_text,
                'x': bbox[0],
                'y': bbox[1],
                'is_correct': has_correct,
                'is_incorrect': has_incorrect,
            })

    # Sort by y first (top to bottom), then x (left to right)
    return sorted(blocks, key=lambda b: (b['y'], b['x']))
```

---

## Skip/Filter Patterns

### Header/Footer Detection

```python
def is_header_footer(text):
    text = text.strip()
    if re.match(r'^LPG\d+', text):       # Course code header
        return True
    if re.match(r'^\d+/\d+$', text):     # Page numbers "5/42"
        return True
    if 'Candidate' in text:              # Candidate info
        return True
    if 'Digital tentamen' in text:       # Exam header
        return True
    return False
```

### Skippable Content

```python
def is_skippable(text):
    text = text.strip()
    if text.startswith('Ord:'):                    # Word count
        return True
    if text == 'Skriv in ditt svar här':          # Input placeholder
        return True
    if text.startswith('Bifoga ritning'):          # Drawing instruction
        return True
    if text.startswith('Använd följande kod:'):    # Code instruction
        return True
    if re.match(r'^[\d\s]+$', text):              # Only digits/spaces
        return True
    return False
```

---

## Complete Processing Pipeline

```python
def parse_exam(pdf_path):
    doc = fitz.open(pdf_path)

    # 1. Format detection
    format = detect_format(doc)
    thresholds = FORMATS[format]

    # 2. Metadata extraction
    metadata = parse_metadata(doc[0])

    # 3. TOC parsing (question types)
    question_types = parse_toc(doc)

    # 4. Find first question page
    start_page = find_first_question_page(doc)

    # 5. Parse questions
    questions = []
    current_question = None
    current_text_parts = []
    current_options = []
    seen_questions = set()

    for page_num in range(start_page, len(doc)):
        page = doc[page_num]
        blocks = get_sorted_blocks(page)

        for block in blocks:
            text = block['text'].strip()
            x = block['x']

            if not text or is_header_footer(text):
                continue

            # Question number zone
            if x < thresholds['X_QUESTION_NUMBER']:
                q_match = re.match(r'^(\d{1,3})(?:\s+(.*))?$', text)
                if q_match:
                    q_num = int(q_match.group(1))
                    if 1 <= q_num <= 100 and q_num not in seen_questions:
                        # Finalize previous question
                        if current_question:
                            finalize_question(current_question, current_text_parts, current_options)
                            questions.append(current_question)

                        # Start new question
                        seen_questions.add(q_num)
                        current_question = Question(
                            number=q_num,
                            question_type=question_types.get(q_num, 'Okänd'),
                            category=extract_category(q_match.group(2) or "")
                        )
                        current_text_parts = []
                        current_options = []
                        continue

            # Must have a current question for the rest
            if not current_question:
                continue

            # Points extraction
            if 'Totalpoäng:' in text:
                match = re.search(r'Totalpoäng:\s*(\d+(?:[.,]\d+)?)', text)
                if match:
                    current_question.points = float(match.group(1).replace(',', '.'))

            # Option zone
            elif x >= thresholds['X_OPTION'] and looks_like_option(text):
                opt = parse_option(text, block['is_correct'])
                if opt:
                    current_options.append(opt)

            # Question text zone
            elif not is_skippable(text):
                current_text_parts.append(text)

    # Finalize last question
    if current_question:
        finalize_question(current_question, current_text_parts, current_options)
        questions.append(current_question)

    # Filter empty questions
    questions = [q for q in questions if q.text.strip()]

    doc.close()
    return ParsedExam(
        filename=pdf_path.name,
        metadata=metadata,
        questions=questions
    )
```

---

## Edge Cases

### 1. MCQ with Zero Options (Actually Short Answer)

Some questions marked as "Flervalsfråga" in TOC are actually short-answer format.

```python
# If MCQ has 0 options, try to extract answer from text
mcq_types = ['Flervalsfråga', 'Flersvarsfråga', 'Okänd']
if question.question_type in mcq_types and len(options) == 0:
    # Try labeled sub-questions "A. content B. content"
    labeled = re.findall(r'([A-Z])\.\s*(.+?)(?=\s+[A-Z]\.\s|$)', full_text + ' ')
    if len(labeled) >= 2:
        answer_text = ' | '.join([m[1].strip() for m in labeled])

    # Try "?" followed by answer
    if not answer_text and '?' in full_text:
        parts = full_text.rsplit('?', 1)
        if len(parts) > 1 and len(parts[1].strip()) > 5:
            answer_text = parts[1].strip()
```

### 2. Essay Options That Are Actually Answers

Essay questions sometimes have "options" that are actually numbered answer parts.

```python
essay_types = ['Essä', 'Essäfråga', 'Kortsvarsfråga', 'Textområde']
if question.question_type in essay_types and options:
    opt_texts = [o.text for o in options]
    combined = ' '.join(opt_texts)

    # Check for numbered pattern "1. answer 2. answer"
    has_numbered = re.search(r'\d+[.:]\s*\w', combined)
    has_correct_markers = any(o.is_correct for o in options)

    if has_numbered or (len(options) <= 3 and not has_correct_markers):
        answer_text = combined
        options = []  # Clear options
```

### 3. Hotspot Answer Extraction (100% coverage achieved)

Hotspot answers are marked by **blue regions** on the page - either filled rectangles or stroke outlines.

```python
def _get_blue_regions(self, page) -> list[tuple]:
    """Get blue highlighted regions (hotspot answers).
    Returns list of (x, y, w, h) tuples."""
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
            # Filter: allow small markers (5x5+) up to large regions
            if (5 < w < 400 and 5 < h < 400):
                blue_regions.append((int(x), int(y), int(w), int(h)))
    return blue_regions
```

**Blue Region Types:**
- **Small markers**: ~20x10 pixels (checkmark-sized)
- **Wide bars**: ~60x8 pixels (horizontal highlight)
- **Large circles**: ~30x30 pixels (circle outline)

**XML Example:**
```xml
<drawings>
  <!-- Blue filled rectangle marking hotspot answer -->
  <path fill="(0.05, 0.60, 0.94)" rect="(281, 193, 302, 203)"/>
  <!-- Green checkmark confirming correct answer -->
  <path fill="(0.21, 0.55, 0.08)" rect="(288, 196, 296, 202)"/>
</drawings>
```

**Fallback:** If no blue regions found, extract number/letter after question mark.

---

## Blacklisted Files

These merged exam collections duplicate content and should be skipped:

```python
BLACKLIST = {
    'YZf9yLAXGlkpSbQ9GKlt_Tentor_med_svar.pdf',
    '7I3UGkJgSQcYE18EYYMR_Tentor_med_svar.pdf',
    'LCjrBjJiquEd9Vv2c24A_Tentor_med_svar.pdf',
    'tUEMcmS1CrYLJ1LWhpqG_Tentor_med_svar_.pdf',
}
```

Pattern: Files with `Tentor_med_svar` are merged collections.

---

## Current Coverage by Type (January 2025)

| Type | Swedish | Coverage | Missing | Notes |
|------|---------|----------|---------|-------|
| hot | Hotspot | 100% | 0 | ✅ Complete! |
| tf | Sant/Falskt | 100% | 0 | ✅ Complete! |
| mc1 | Flervalsfråga | 99.5% | 17 | Single-choice MCQ |
| ess | Essäfråga | 99.6% | 10 | Essays |
| mcn | Flersvarsfråga | 98.9% | 14 | Multi-choice MCQ |
| unk | Okänd | 97.2% | 1 | Unknown types |
| drop | Textalternativ | 96.5% | 3 | Dropdowns |
| drag | Dra och släpp | 95.8% | 6 | Drag & drop |
| match | Matchning | 88.4% | 11 | Matching tables |
| **txt** | Textområde | **83.1%** | **61** | Text labeling |

**Total: 8127/8250 questions (98.5%)**

**Priority:** txt (61 missing), match (11 missing)

---

## Output YAML Format

```yaml
exam:
  id: ah1_2310_a1b2
  course: ah1
  date: "17.10.2023"
  file: exam.pdf

q:
  num: 1
  type: mc1
  type_full: Flervalsfråga
  pts: 1.0
  cat: Rörelseapparaten
  text: "Vilken muskel är primär flexor av armbågen?"
  opts:
    - "M. biceps brachii"
    - "M. triceps brachii"
    - "M. brachialis"
  correct: 0  # Index for mc1, list for mcn
```

---

## Testing Recommendations

1. **Run coverage check after every change:**
   ```bash
   uv run disa.py -v
   ```

2. **Never decrease coverage** - any change that reduces total coverage is a regression

3. **Test on edge cases:**
   - Image-based MCQ with single-letter options (A-E)
   - TOC with non-standard column positions
   - Essay questions with numbered sub-answers
   - Hotspot questions with coordinate answers

4. **Blacklist merged exam collections** to avoid duplicate counting
