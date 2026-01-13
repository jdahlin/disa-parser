# Question YAML Format

Each question is exported as a single YAML file: `{exam_id}_q{num}_{type}.yaml`

## Structure

```yaml
exam:
  id: ah1_2310_7283       # course_YYMM_hash
  course: ah1             # 3-letter code
  date: 17.10.2023
  file: original.pdf

q:
  num: 1                  # Question number
  type: mc1               # Type code (see below)
  type_full: Flervalsfråga
  pts: 1.0
  text: "Question text here"
  cat: Rörelseapparaten   # Category (optional)

  # For MCQ (mc1, mcn, tf):
  opts:
    - text: "Option A"
      correct: true
    - text: "Option B"
  correct: 0              # Index of correct option (mc1)

  # For essay/text (ess, txt, short):
  answer: "Student's answer text"
```

## Type Codes

| Code | Swedish | Description |
|------|---------|-------------|
| mc1 | Flervalsfråga | Single-choice MCQ |
| mcn | Flersvarsfråga | Multi-choice MCQ |
| tf | Sant/Falskt | True/False |
| ess | Essä/Essäfråga | Essay |
| txt | Textområde | Text area (labeling) |
| match | Matchning | Matching |
| hot | Hotspot | Image click |
| drag | Dra och släpp | Drag & drop |
| drop | Textalternativ | Dropdown |
| unk | Okänd | Unknown |

## Examples

### mc1 - Single Choice
```yaml
exam:
  id: ah1_2310_7283
  course: ah1
  date: 17.10.2023
  file: exam.pdf
q:
  num: 3
  type: mc1
  type_full: Flervalsfråga
  pts: 1.0
  text: Vilket av följande påståenden är rätt?
  cat: Rörelseapparaten
  opts:
    - text: en muskel som förlänger tungroten
    - text: en muskel som sträcker handleden
      correct: true
    - text: en sena som spänner trumhinnan
  correct: 1
```

### mcn - Multiple Choice
```yaml
q:
  num: 11
  type: mcn
  type_full: Flersvarsfråga
  pts: 1.0
  text: "Vad är korrekt om retikulära fibrer? Välj två:"
  opts:
    - text: Kan särskiljas i H/E-färgning
    - text: Bildar fibernätverk i mjälten
      correct: true
    - text: Består av typ 3-kollagen
      correct: true
  correct: [1, 2]
```

### ess - Essay
```yaml
q:
  num: 8
  type: ess
  type_full: Essä
  pts: 3.0
  text: |
    Beskriv kort uppbyggnaden av:
    a) Enkelt skivepitel
    b) Övergångsepitel
  cat: Histologi
  answer: |
    a) Enkelt skivepitel består av ett lager platta celler...
    b) Övergångsepitel har flera lager med paraplyceller...
```

### txt - Text Area (Labeling)
```yaml
q:
  num: 7
  type: txt
  type_full: Textområde
  pts: 2.0
  text: "Namnge strukturerna 1-4 i bilden"
  answer: "1: SA-knutan | 2: AV-knutan | 3: His bunt | 4: Purkinjefibrer"
```

### match - Matching
```yaml
q:
  num: 6
  type: match
  type_full: Matchning
  pts: 2.0
  text: "Para ihop strukturerna med rätt lägesord"
  opts:
    - text: "Pulmo dexter → Medialt"
      correct: true
    - text: "Sternum → Ventralt"
      correct: true
```

### hot - Hotspot
```yaml
q:
  num: 13
  type: hot
  type_full: Hotspot
  pts: 2.0
  text: "Vilken siffra markerar förkalkningszonen?"
  correct: 4
```

## Answer Fields

| Type | Answer Location |
|------|-----------------|
| mc1, mcn, tf | `correct` (index) + `opts[].correct` |
| ess, txt | `answer` (text) |
| match | `opts[].correct` |
| hot | `correct` (region number) |
| drag, drop | `opts[].correct` or `answer` |
