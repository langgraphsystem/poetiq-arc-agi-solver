# Analytics Agent

## Purpose

Performance analysis and **iterative optimization** of listings. Uses the iterative refinement pattern from ARC-AGI Solver to automatically improve underperforming listings.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ANALYTICS AGENT                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              PERFORMANCE ANALYSIS                    │   │
│  │         (Claude Opus 4.5 + effort=high)             │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              ISSUE IDENTIFICATION                    │   │
│  │         Low conversion? Bad tags? Short desc?        │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           ITERATIVE REFINEMENT (ARC-AGI)            │   │
│  │                                                      │   │
│  │   Iteration 1 ──► Score ──► Feedback ──►            │   │
│  │   Iteration 2 ──► Score ──► Feedback ──►            │   │
│  │   ...                                                │   │
│  │   Until score >= 0.90 or max_iterations             │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              OPTIMIZED CONTENT                       │   │
│  │         Title + Tags + Description                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Iterative Refinement (from ARC-AGI)

```python
result = await iterative_refinement(
    initial_output=current_content,
    task={"performance": performance, "issues": issues},
    refine_fn=refine_content,      # LLM improves content
    score_fn=score_content,        # Score quality 0-1
    max_iterations=5,
    target_score=0.90,             # Stop when reached
)

# Result contains:
# - output: best optimized content
# - final_score: achieved score
# - iterations_used: how many iterations
# - improvement_history: [0.5, 0.65, 0.78, 0.92]
```

## Performance Classification

| Level | Conversion Rate | Action |
|-------|-----------------|--------|
| Excellent | ≥ 3.0% | Monitor only |
| Good | ≥ 2.0% | Minor tweaks |
| Average | ≥ 1.0% | Consider optimization |
| Poor | ≥ 0.5% | **Auto-optimize** |
| Critical | < 0.5% | **Priority optimization** |

## Usage

```python
from agents.analytics import AnalyticsAgent, ListingPerformance

agent = AnalyticsAgent()

# Create performance object
performance = ListingPerformance(
    listing_id="123456",
    title="Custom Star Map Print",
    views=500,
    favorites=15,
    orders=2,
    revenue=59.98,
)

print(f"Level: {performance.level}")  # POOR
print(f"Needs optimization: {performance.needs_optimization}")  # True

# Analyze
analysis = await agent.analyze(performance)
print(analysis["issues"])
print(analysis["recommendations"])

# Optimize with iterative refinement
result = await agent.optimize(
    listing_id="123456",
    current_content={
        "title": "Star Map",  # Too short!
        "tags": ["star", "map"],  # Only 2 tags!
        "description": "Nice star map.",  # Too short!
    },
    performance=performance,
    max_iterations=5,
)

print(f"Iterations: {result.iterations_used}")
print(f"Score improvement: {result.score_improvement:.2f}")
print(f"New title: {result.optimized_title}")
```

## Batch Optimization

```python
from agents.analytics import batch_optimize

# Optimize multiple listings concurrently
results = await batch_optimize(
    listings=[
        {"id": "123", "content": {...}, "performance": perf1},
        {"id": "456", "content": {...}, "performance": perf2},
    ],
    max_concurrent=3,
    max_iterations_per_listing=3,
)

for r in results:
    print(f"{r.listing_id}: {r.score_improvement:.2f} improvement")
```

## Model Selection

| Task | Model | Why |
|------|-------|-----|
| **Deep Analysis** | Claude Opus 4.5 (effort=high) | Comprehensive insights |
| **Optimization** | Claude Sonnet 4.5 | Fast iteration |
| **Scoring** | Local function | No API needed |

## Output Format

```python
@dataclass
class OptimizationResult:
    listing_id: str
    original_title: str
    optimized_title: str
    original_tags: list[str]
    optimized_tags: list[str]
    original_description: str
    optimized_description: str
    issues_found: list[str]
    improvements_made: list[str]
    iterations_used: int
    final_score: float
    score_improvement: float
    total_tokens: int
```

## Files

```
agents/analytics/
├── CLAUDE.md       # This file
├── __init__.py     # Exports
└── agent.py        # Main implementation
    ├── ListingPerformance   # Metrics data model
    ├── OptimizationResult   # Output data model
    ├── analyze_listing()    # Deep analysis
    ├── optimize_underperforming()  # Iterative optimization
    └── batch_optimize()     # Concurrent batch processing
```
