"""
Parallel Expert Pattern for Content Generation
Adapted from ARC-AGI Solver (solve_parallel_coding.py)

This module provides multi-expert parallel generation with voting
for selecting the best content variants.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar, Literal
from enum import Enum

T = TypeVar('T')


class ContentType(Enum):
    """Types of content that can be generated"""
    TITLE = "title"
    TAGS = "tags"
    DESCRIPTION = "description"
    FAQ = "faq"


@dataclass
class ExpertConfig:
    """
    Configuration for a single expert.
    Adapted from ARC-AGI ExpertConfig.
    """
    # Model settings
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096

    # Expert identity
    expert_id: str = ""
    style: str = ""  # e.g., "creative", "seo_focused", "emotional"

    # Iteration settings (for refinement)
    max_iterations: int = 1
    seed: int = 0

    # Voting settings
    use_voting: bool = True

    # Additional model-specific params
    extra_params: dict = field(default_factory=dict)


@dataclass
class ExpertResult(Generic[T]):
    """
    Result from a single expert.
    Tracks output, quality score, and resource usage.
    """
    output: T
    score: float  # Quality score 0.0 - 1.0
    expert_id: str
    iteration: int = 1

    # Token tracking (from ARC-AGI)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Metadata
    model: str = ""
    duration_sec: float = 0.0

    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class VotingResult(Generic[T]):
    """
    Aggregated result after voting.
    Contains ranked list of results with vote counts.
    """
    ranked_results: list[ExpertResult[T]]
    vote_counts: dict[str, int]  # canonical_key -> count
    total_tokens: int
    total_duration_sec: float

    @property
    def best(self) -> ExpertResult[T] | None:
        """Get the top-ranked result"""
        return self.ranked_results[0] if self.ranked_results else None

    @property
    def top_n(self) -> Callable[[int], list[ExpertResult[T]]]:
        """Get top N results"""
        def _get(n: int) -> list[ExpertResult[T]]:
            return self.ranked_results[:n]
        return _get


def canonical_key(output: Any, content_type: ContentType) -> str:
    """
    Create a hashable key for grouping similar outputs.
    Adapted from ARC-AGI utils.canonical_test_key
    """
    if output is None:
        return "__none__"

    if content_type == ContentType.TITLE:
        # Normalize title for comparison
        if isinstance(output, str):
            return output.lower().strip()[:50]
        return str(output)[:50]

    elif content_type == ContentType.TAGS:
        # Sort tags for consistent comparison
        if isinstance(output, list):
            return "|".join(sorted([str(t).lower().strip() for t in output]))
        return str(output)

    elif content_type == ContentType.DESCRIPTION:
        # Use first 100 chars for grouping
        if isinstance(output, str):
            return output.lower().strip()[:100]
        return str(output)[:100]

    else:
        return str(output)[:100]


async def solve_with_parallel_experts(
    task: dict[str, Any],
    expert_configs: list[ExpertConfig],
    solver_fn: Callable[[dict, ExpertConfig], Any],
    score_fn: Callable[[Any], float],
    content_type: ContentType,
    use_voting: bool = True,
    count_failed: bool = True,
) -> VotingResult:
    """
    Run multiple experts in parallel and aggregate results via voting.

    Core algorithm adapted from ARC-AGI solve_parallel_coding.py:
    1. Run all experts concurrently
    2. Group results by canonical output key (voting buckets)
    3. Separate into passers (score >= threshold) and failures
    4. Rank by vote count (diversity-first)
    5. Return ordered results

    Args:
        task: The generation task (product info, keywords, etc.)
        expert_configs: List of expert configurations
        solver_fn: Async function(task, config) -> ExpertResult
        score_fn: Function to score output quality (0.0 - 1.0)
        content_type: Type of content being generated
        use_voting: Whether to use voting aggregation
        count_failed: Include failed results in voting counts

    Returns:
        VotingResult with ranked results and metadata
    """
    # Ensure unique seeds per expert (from ARC-AGI)
    for i, cfg in enumerate(expert_configs):
        cfg.seed += i * cfg.max_iterations
        if not cfg.expert_id:
            cfg.expert_id = f"expert_{i}"

    # Run all experts concurrently
    tasks = [
        asyncio.create_task(solver_fn(task, cfg))
        for cfg in expert_configs
    ]
    results: list[ExpertResult] = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions
    valid_results = []
    for r in results:
        if isinstance(r, Exception):
            print(f"Expert failed with: {r}")
            continue
        valid_results.append(r)

    if not valid_results:
        return VotingResult(
            ranked_results=[],
            vote_counts={},
            total_tokens=0,
            total_duration_sec=0.0
        )

    # Calculate totals
    total_tokens = sum(r.total_tokens() for r in valid_results)
    total_duration = sum(r.duration_sec for r in valid_results)

    if not use_voting:
        # Simple sort by score
        valid_results.sort(key=lambda r: r.score, reverse=True)
        return VotingResult(
            ranked_results=valid_results,
            vote_counts={},
            total_tokens=total_tokens,
            total_duration_sec=total_duration
        )

    # === VOTING ALGORITHM (from ARC-AGI) ===

    # Group by canonical key
    passer_buckets: dict[str, list[ExpertResult]] = defaultdict(list)
    failure_buckets: dict[str, list[ExpertResult]] = defaultdict(list)

    PASS_THRESHOLD = 0.7  # Score threshold for "passing"

    for res in valid_results:
        key = canonical_key(res.output, content_type)
        if res.score >= PASS_THRESHOLD:
            passer_buckets[key].append(res)
        else:
            failure_buckets[key].append(res)

    # Optionally merge failures into passers if outputs match
    if count_failed:
        for key in list(failure_buckets.keys()):
            if key in passer_buckets:
                passer_buckets[key].extend(failure_buckets[key])
                del failure_buckets[key]

    # Sort passers: by vote count (desc), then by score within group
    passer_groups: list[list[ExpertResult]] = list(passer_buckets.values())
    for group in passer_groups:
        group.sort(key=lambda r: r.score, reverse=True)
    passer_groups.sort(key=len, reverse=True)

    # Sort failures: by score
    failure_groups: list[list[ExpertResult]] = list(failure_buckets.values())
    for group in failure_groups:
        group.sort(key=lambda r: r.score, reverse=True)
    failure_groups.sort(
        key=lambda g: (len(g), g[0].score if g else 0.0),
        reverse=True
    )

    # Build ordered list (diversity-first)
    ordered: list[ExpertResult] = []

    # 1. First from each passer group (diversity)
    ordered.extend([g[0] for g in passer_groups if g])

    # 2. First from each failure group
    ordered.extend([g[0] for g in failure_groups if g])

    # 3. Remaining passer members
    ordered.extend([r for g in passer_groups for r in g[1:]])

    # 4. Remaining failure members
    ordered.extend([r for g in failure_groups for r in g[1:]])

    # Calculate vote counts
    vote_counts = {k: len(v) for k, v in passer_buckets.items()}
    vote_counts.update({k: len(v) for k, v in failure_buckets.items()})

    return VotingResult(
        ranked_results=ordered,
        vote_counts=vote_counts,
        total_tokens=total_tokens,
        total_duration_sec=total_duration
    )


# === ITERATIVE REFINEMENT (from ARC-AGI solve_coding.py) ===

@dataclass
class RefinementResult(Generic[T]):
    """Result of iterative refinement"""
    output: T
    final_score: float
    iterations_used: int
    improvement_history: list[float]
    total_tokens: int


async def iterative_refinement(
    initial_output: T,
    task: dict[str, Any],
    refine_fn: Callable[[T, dict, str], Any],  # (current, task, feedback) -> improved
    score_fn: Callable[[T], float],
    max_iterations: int = 5,
    target_score: float = 0.95,
    early_stop: bool = True,
) -> RefinementResult[T]:
    """
    Iteratively refine output using feedback.
    Adapted from ARC-AGI solve_coding.py iteration loop.

    Args:
        initial_output: Starting output to refine
        task: Original task context
        refine_fn: Async function(current, task, feedback) -> improved output
        score_fn: Function to score quality
        max_iterations: Maximum refinement iterations
        target_score: Stop when this score is reached
        early_stop: Whether to stop early on target_score

    Returns:
        RefinementResult with best output and history
    """
    current = initial_output
    best_output = current
    best_score = score_fn(current)

    history = [best_score]
    total_tokens = 0

    for iteration in range(max_iterations):
        # Generate feedback based on current score
        feedback = _generate_feedback(current, best_score, task)

        # Refine
        result = await refine_fn(current, task, feedback)

        if isinstance(result, ExpertResult):
            current = result.output
            total_tokens += result.total_tokens()
        else:
            current = result

        score = score_fn(current)
        history.append(score)

        if score > best_score:
            best_output = current
            best_score = score

        # Early exit if target reached
        if early_stop and best_score >= target_score:
            break

    return RefinementResult(
        output=best_output,
        final_score=best_score,
        iterations_used=len(history) - 1,
        improvement_history=history,
        total_tokens=total_tokens
    )


def _generate_feedback(current: Any, score: float, task: dict) -> str:
    """Generate feedback for refinement iteration"""
    feedback_parts = []

    if score < 0.5:
        feedback_parts.append("The current output needs significant improvement.")
    elif score < 0.8:
        feedback_parts.append("The output is good but can be better.")
    else:
        feedback_parts.append("The output is almost perfect, minor tweaks needed.")

    feedback_parts.append(f"Current quality score: {score:.2f}")

    # Add task-specific feedback hints
    if "keywords" in task:
        feedback_parts.append(f"Ensure keywords are included: {task['keywords'][:3]}")

    return " ".join(feedback_parts)


# === PRESET EXPERT CONFIGURATIONS ===

def get_title_expert_configs() -> list[ExpertConfig]:
    """Preset configs for title generation with diversity"""
    return [
        ExpertConfig(
            model="gpt-5-mini",
            temperature=0.9,
            expert_id="creative",
            style="creative",
            extra_params={}
        ),
        ExpertConfig(
            model="gpt-5-mini",
            temperature=0.5,
            expert_id="seo_focused",
            style="seo_focused",
            extra_params={}
        ),
        ExpertConfig(
            model="claude-sonnet-4-5-20250929",
            temperature=0.7,
            expert_id="emotional",
            style="emotional",
            extra_params={"thinking": {"type": "enabled", "budget_tokens": 5000}}
        ),
    ]


def get_description_expert_configs() -> list[ExpertConfig]:
    """Preset configs for description generation"""
    return [
        ExpertConfig(
            model="claude-sonnet-4-5-20250929",
            temperature=0.7,
            expert_id="narrative",
            style="emotional_narrative",
            max_tokens=2000,
        ),
        ExpertConfig(
            model="gpt-5-mini",
            temperature=0.6,
            expert_id="benefits",
            style="benefits_focused",
            max_tokens=2000,
        ),
    ]
