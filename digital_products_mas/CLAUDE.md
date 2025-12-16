# Digital Products Multi-Agent System

## Overview

**9-agent AI system** for automated creation and sales of digital products and POD items. Built with patterns adapted from the **ARC-AGI Solver** (Poetiq).

## Key Patterns from ARC-AGI

| Pattern | Source | Application |
|---------|--------|-------------|
| **Parallel Expert Voting** | `solve_parallel_coding.py` | Content Creator generates multiple variants, votes for best |
| **Iterative Refinement** | `solve_coding.py` | Analytics optimizes underperforming listings |
| **Sandbox Execution** | `sandbox.py` | Artisan safely runs generated code |
| **Rate Limiting** | `llm.py` | All API calls rate-limited per model |
| **Token Tracking** | `llm.py` | Session-wide cost tracking |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                           │
│                  (LangGraph + Claude Opus 4.5)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
    ▼                 ▼                 ▼
┌─────────┐    ┌───────────┐    ┌─────────────┐
│RESEARCH │    │ CREATION  │    │DISTRIBUTION │
│ LAYER   │    │   LAYER   │    │   LAYER     │
├─────────┤    ├───────────┤    ├─────────────┤
│Trend    │    │Artisan    │    │Listing      │
│Market   │    │Content    │    │Fulfillment  │
│Ingestion│    │Mockup     │    │Analytics    │
└─────────┘    └───────────┘    └─────────────┘
```

## Agents Implemented

| Agent | Status | Key Feature |
|-------|--------|-------------|
| **Content Creator** | ✅ | Multi-expert voting for titles/descriptions |
| **Artisan** | ✅ | Sandbox execution for safe file generation |
| **Analytics** | ✅ | Iterative refinement for optimization |
| **Orchestrator** | ✅ | LangGraph workflow |

## Tech Stack

- **Python 3.11+**
- **LangGraph** — Workflow orchestration
- **OpenAI** — GPT-5, Sora, GPT-Image-1
- **Anthropic** — Claude Opus 4.5, Sonnet 4.5
- **Google** — Gemini 3, Imagen 4, Veo 3
- **asynciolimiter** — Rate limiting

## Model Selection Strategy

| Task | Model | Why |
|------|-------|-----|
| Orchestration | Claude Opus 4.5 | Best planning |
| Research | Gemini 3 Pro | 1M context, web grounding |
| Code | Claude Sonnet 4.5 | SWE-bench leader |
| Titles | GPT-5 Mini | Creative |
| **Tags** | **Gemini 2.5 Flash** | **Best at 20-char limit** |
| Descriptions | Claude Sonnet 4.5 | Narrative |
| Images | GPT-Image-1 / Imagen 4 | Quality |
| Video | Veo 3 | Native audio |
| Analysis | Claude Opus 4.5 (effort=high) | Deep reasoning |

## Directory Structure

```
digital_products_mas/
├── CLAUDE.md                 # This file
├── __init__.py
├── core/
│   ├── parallel_experts.py   # Voting from ARC-AGI
│   ├── rate_limiter.py       # Rate limiting from ARC-AGI
│   └── sandbox.py            # Safe execution from ARC-AGI
├── integrations/
│   ├── openai_client.py      # GPT-5, Sora, Images
│   ├── anthropic_client.py   # Claude Opus/Sonnet
│   ├── google_client.py      # Gemini, Imagen, Veo
│   └── unified_llm.py        # Unified interface
├── agents/
│   ├── content_creator/      # SEO content with voting
│   ├── artisan/              # File generation with sandbox
│   └── analytics/            # Performance optimization
├── orchestrator/
│   ├── state.py              # Workflow state
│   └── graph.py              # LangGraph workflow
└── examples/
    └── content_generation.py
```

## Quick Start

```python
# Process an order
from digital_products_mas.orchestrator import process_order

result = await process_order(
    order_id="ORD-001",
    order_data={
        "products": [
            {
                "sku": "STAR-MAP-001",
                "name": "Custom Star Map",
                "params": {"lat": 40.7, "lon": -74.0, "datetime": "2024-01-15"}
            }
        ]
    }
)

print(f"Status: {result['status']}")
print(f"Files: {result['generated_files']}")
```

## Environment Variables

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
GCP_PROJECT=your-project-id  # For Imagen/Veo
```

## Cost Estimation (per 1000 orders)

| Component | Model | Cost |
|-----------|-------|------|
| Content | Claude Sonnet | ~$0.30 |
| Tags | Gemini Flash | ~$0.01 |
| Images | GPT-Image-1 | ~$0.04 |
| **Total** | | **~$0.35/order** |

## Code Conventions

- Type hints everywhere
- Async by default
- Dataclasses for data models
- Structured logging

## Running Tests

```bash
cd digital_products_mas
python -m pytest tests/
```

## References

- [ARC-AGI Solver](../) — Source of core patterns
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [OpenAI API](https://platform.openai.com/docs)
- [Anthropic API](https://docs.anthropic.com)
- [Google AI](https://ai.google.dev/docs)
