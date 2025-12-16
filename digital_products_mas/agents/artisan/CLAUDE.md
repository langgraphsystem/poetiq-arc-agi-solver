# Artisan Agent

## Purpose

Core file generation engine. Routes orders to appropriate generators based on SKU pattern. Uses **sandbox execution** (adapted from ARC-AGI) for safe code execution.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ARTISAN AGENT                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────┐                                          │
│   │  SKU Router │                                          │
│   └──────┬──────┘                                          │
│          │                                                  │
│   ┌──────┴──────────────────────────────────────┐          │
│   │                                              │          │
│   ▼              ▼              ▼               ▼          │
│ ┌──────┐    ┌──────┐    ┌──────────┐    ┌──────────┐      │
│ │STAR  │    │PLAN- │    │WALL-ART  │    │VIDEO     │      │
│ │MAP   │    │NER   │    │          │    │          │      │
│ └──┬───┘    └──┬───┘    └────┬─────┘    └────┬─────┘      │
│    │           │             │               │             │
│    ▼           ▼             ▼               ▼             │
│ ┌──────┐  ┌──────┐    ┌──────────┐    ┌──────────┐        │
│ │SAND- │  │SAND- │    │GPT-Image │    │Veo 3 /   │        │
│ │BOX   │  │BOX   │    │/ Imagen  │    │Sora      │        │
│ └──────┘  └──────┘    └──────────┘    └──────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## SKU Routing

| SKU Pattern | Generator | Technology | Output |
|-------------|-----------|------------|--------|
| `STAR-MAP-*` | `generate_star_map()` | Skyfield + Matplotlib (sandbox) | PNG 300dpi |
| `PLANNER-*` | `generate_planner()` | ReportLab (sandbox) | PDF |
| `WALL-ART-*` | `generate_wall_art()` | GPT-Image-1 / Imagen 4 | PNG |
| `VIDEO-*` | `generate_product_video()` | Veo 3 / Sora | MP4 |

## Sandbox Execution (from ARC-AGI)

Code runs in isolated subprocess:

```python
from core.sandbox import run_code

result = await run_code(
    code=generated_python_code,
    input_data={"lat": 40.7, "lon": -74.0},
    timeout_sec=60.0,
)

if result.success:
    output = result.output
else:
    error = result.error
```

**Security:**
- Subprocess isolation (not in-process)
- Temporary directory
- Timeout with process kill
- PYTHONHASHSEED=0 for reproducibility

## Model Selection

| Task | Primary Model | Fallback |
|------|---------------|----------|
| **Wall Art** | GPT-Image-1 | Imagen 4 Ultra |
| **Artistic Images** | Imagen 4 Ultra | GPT-Image-1 |
| **Video** | Veo 3 (has audio!) | Sora |
| **Video from Image** | Veo 3.1 | Sora |

## Usage

```python
from agents.artisan import ArtisanAgent

agent = ArtisanAgent()

# Route by SKU
file = await agent.generate(
    sku="STAR-MAP-001",
    params={
        "lat": 40.7128,
        "lon": -74.0060,
        "datetime": "2024-01-15 22:00",
        "title": "The Night We Met",
    }
)

# Save file
path = file.save("output/")
print(f"Generated: {path} ({file.size_kb:.1f} KB)")
```

## Output Format

```python
@dataclass
class GeneratedFile:
    path: str           # Filename
    file_bytes: bytes   # Raw file data
    metadata: dict      # Generation params, format, etc.

    def save(output_dir: str) -> str  # Save to disk
    def size_kb -> float              # Size in KB
    def checksum -> str               # MD5 hash
```

## Quality Checks

- **DPI verification**: 300 for print
- **Color profile**: sRGB (digital), CMYK (print)
- **Dimension validation**: Match expected aspect ratio
- **File size limits**: Min/max per product type

## Files

```
agents/artisan/
├── CLAUDE.md           # This file
├── __init__.py         # Exports
├── agent.py            # Main implementation
└── generators/         # Specialized generators
    ├── star_map.py     # Skyfield integration
    ├── planner_pdf.py  # ReportLab templates
    └── video_promo.py  # Video generation
```

## Error Handling

```python
try:
    file = await agent.generate(sku, params)
except RuntimeError as e:
    # Generation failed in sandbox
    logger.error(f"Generation failed: {e}")
    # Retry with fallback or alert
```

Retry strategy:
- 3x with exponential backoff
- Fallback to alternative generator
- Alert on repeated failures
