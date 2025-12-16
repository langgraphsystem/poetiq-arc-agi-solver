# Content Creator Agent

## Purpose

Generate SEO-optimized listing content for e-commerce marketplaces using **multi-expert parallel generation with voting** — adapted from ARC-AGI Solver patterns.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT CREATOR                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │  Expert 1   │   │  Expert 2   │   │  Expert 3   │       │
│  │ GPT-5-mini  │   │ GPT-5-mini  │   │Claude Sonnet│       │
│  │ creative    │   │ seo_focused │   │ emotional   │       │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘       │
│         │                 │                 │               │
│         └────────────┬────┴────────────────┘               │
│                      ▼                                      │
│              ┌──────────────┐                               │
│              │   VOTING     │                               │
│              │  (ARC-AGI)   │                               │
│              └──────┬───────┘                               │
│                     ▼                                       │
│              ┌──────────────┐                               │
│              │ Top 3 Titles │                               │
│              └──────────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

## Multi-Model Strategy

| Task | Model | Why |
|------|-------|-----|
| **Titles** | GPT-5 Mini (×2) + Claude Sonnet | Diversity via temperature & style |
| **Tags** | Gemini 2.5 Flash | **Best at 20-char limit compliance** |
| **Description** | Claude Sonnet 4.5 | Emotional narrative, long-form |
| **FAQ** | GPT-4.1 Nano | Fast, cheap Q&A |
| **Optimization** | Claude Sonnet 4.5 + iterative | Deep refinement |

## Key Patterns (from ARC-AGI)

### 1. Parallel Expert Voting

```python
# Multiple experts generate titles in parallel
title_result = await solve_with_parallel_experts(
    task={"product": product},
    expert_configs=[
        ExpertConfig(model="gpt-5-mini", temperature=0.9, style="creative"),
        ExpertConfig(model="gpt-5-mini", temperature=0.5, style="seo_focused"),
        ExpertConfig(model="claude-sonnet-4-5", temperature=0.7, style="emotional"),
    ],
    solver_fn=solve_title,
    score_fn=lambda t: score_title(t, product),
    content_type=ContentType.TITLE,
    use_voting=True,
)

# Results ranked by vote count (diversity-first)
top_titles = [r.output for r in title_result.ranked_results[:3]]
```

### 2. Iterative Refinement

```python
# Optimize underperforming listings
result = await iterative_refinement(
    initial_output=current_description,
    task={"product": product},
    refine_fn=improve_description,  # Uses feedback
    score_fn=score_description,
    max_iterations=5,
    target_score=0.95,  # Stop when quality reached
)
```

### 3. Scoring Functions

```python
def score_title(title: str, product: Product) -> float:
    score = 1.0
    # Length: max 140 chars
    if len(title) > 140: score -= 0.3
    # Primary keyword first
    if not title.lower().startswith(product.keywords[0].lower()):
        score -= 0.2
    return score
```

## Output Specs

| Field | Constraint | Source |
|-------|------------|--------|
| **Title** | max 140 chars, keyword-first | Top voted from 3 experts |
| **Tags** | exactly 13, each ≤20 chars | Gemini 2.5 Flash |
| **Description** | max 2000 chars | Best from 2 experts |
| **FAQ** | 5 Q&A pairs | GPT-4.1 Nano |

## Usage

```python
from agents.content_creator import Product, generate_listing_content

product = Product(
    name="Custom Star Map Print",
    description="Personalized star map for any date and location",
    category="Wall Art",
    keywords=["star map", "anniversary gift", "custom wall art"],
)

content = await generate_listing_content(
    product=product,
    num_title_experts=3,
    use_voting=True,
)

print(content.titles)       # Top 3 titles
print(content.tags)         # 13 tags
print(content.description)  # Best description
print(content.total_tokens) # Token usage
```

## Files

```
agents/content_creator/
├── CLAUDE.md           # This file
├── __init__.py         # Exports
└── agent.py            # Main implementation
    ├── Product         # Data model
    ├── ListingContent  # Output model
    ├── solve_title()   # Expert solver for titles
    ├── solve_tags()    # Expert solver for tags
    ├── solve_description()  # Expert solver for descriptions
    ├── generate_listing_content()  # Main entry point
    └── optimize_listing()  # Iterative refinement
```

## Dependencies

- `core.parallel_experts` — Voting logic from ARC-AGI
- `core.rate_limiter` — Rate limiting & token tracking
- OpenAI, Anthropic, Google API clients

## Etsy SEO Rules

1. **Titles**: Primary keyword FIRST, max 140 chars
2. **Tags**: 13 tags, each ≤20 chars, multi-word only
3. **Description**: Benefits > features, CTA at end
4. No single-word tags
5. Include occasion keywords ("gift for mom")
