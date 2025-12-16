"""
Analytics Agent — Performance Analysis & Iterative Optimization
Uses iterative refinement pattern from ARC-AGI Solver

Key Features:
- Analyze listing performance
- Identify underperforming listings
- Auto-optimize using iterative refinement
- A/B testing recommendations
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Literal
from enum import Enum

from digital_products_mas.core.parallel_experts import (
    iterative_refinement,
    RefinementResult,
)
from digital_products_mas.integrations.unified_llm import llm_call, best_for_task
from digital_products_mas.integrations.anthropic_client import AnthropicClient, ThinkingConfig


class PerformanceLevel(Enum):
    """Performance classification"""
    EXCELLENT = "excellent"  # Top 10%
    GOOD = "good"            # Top 25%
    AVERAGE = "average"      # Middle 50%
    POOR = "poor"            # Bottom 25%
    CRITICAL = "critical"    # Bottom 10%


@dataclass
class ListingPerformance:
    """Performance metrics for a listing"""
    listing_id: str
    title: str

    # Core metrics
    views: int = 0
    favorites: int = 0
    orders: int = 0
    revenue: float = 0.0

    # Calculated metrics
    conversion_rate: float = 0.0  # orders/views
    favorite_rate: float = 0.0    # favorites/views
    avg_order_value: float = 0.0

    # Time period
    period_days: int = 30

    # Classification
    level: PerformanceLevel = PerformanceLevel.AVERAGE

    def __post_init__(self):
        if self.views > 0:
            self.conversion_rate = (self.orders / self.views) * 100
            self.favorite_rate = (self.favorites / self.views) * 100
        if self.orders > 0:
            self.avg_order_value = self.revenue / self.orders

        # Classify performance
        self.level = self._classify()

    def _classify(self) -> PerformanceLevel:
        """Classify performance level"""
        # Based on typical Etsy benchmarks
        if self.conversion_rate >= 3.0:
            return PerformanceLevel.EXCELLENT
        elif self.conversion_rate >= 2.0:
            return PerformanceLevel.GOOD
        elif self.conversion_rate >= 1.0:
            return PerformanceLevel.AVERAGE
        elif self.conversion_rate >= 0.5:
            return PerformanceLevel.POOR
        else:
            return PerformanceLevel.CRITICAL

    @property
    def needs_optimization(self) -> bool:
        """Check if listing needs optimization"""
        return self.level in [PerformanceLevel.POOR, PerformanceLevel.CRITICAL]


@dataclass
class OptimizationResult:
    """Result of listing optimization"""
    listing_id: str
    original_title: str
    optimized_title: str
    original_tags: list[str]
    optimized_tags: list[str]
    original_description: str
    optimized_description: str

    # Analysis
    issues_found: list[str] = field(default_factory=list)
    improvements_made: list[str] = field(default_factory=list)

    # Refinement stats
    iterations_used: int = 0
    final_score: float = 0.0
    score_improvement: float = 0.0

    # Resource usage
    total_tokens: int = 0


class AnalyticsAgent:
    """
    Analytics and optimization agent.

    Uses iterative refinement from ARC-AGI to auto-optimize
    underperforming listings.
    """

    def __init__(self):
        self.anthropic = AnthropicClient()

    async def analyze(self, listing: ListingPerformance) -> dict:
        """
        Deep analysis of listing performance.

        Uses Claude Opus 4.5 with effort=high for comprehensive analysis.
        """
        return await analyze_listing(listing)

    async def optimize(
        self,
        listing_id: str,
        current_content: dict,
        performance: ListingPerformance,
        max_iterations: int = 5,
    ) -> OptimizationResult:
        """
        Optimize a single listing using iterative refinement.
        """
        return await optimize_underperforming(
            listing_id=listing_id,
            current_content=current_content,
            performance=performance,
            max_iterations=max_iterations,
        )

    async def batch_analyze(
        self,
        listings: list[ListingPerformance],
    ) -> dict:
        """Analyze multiple listings and identify patterns"""
        # Identify underperforming
        underperforming = [l for l in listings if l.needs_optimization]

        # Group by performance level
        by_level = {}
        for l in listings:
            level = l.level.value
            if level not in by_level:
                by_level[level] = []
            by_level[level].append(l.listing_id)

        return {
            "total_listings": len(listings),
            "underperforming_count": len(underperforming),
            "by_level": by_level,
            "avg_conversion": sum(l.conversion_rate for l in listings) / len(listings) if listings else 0,
            "total_revenue": sum(l.revenue for l in listings),
        }


# === ANALYSIS FUNCTIONS ===

async def analyze_listing(listing: ListingPerformance) -> dict:
    """
    Deep analysis of a single listing.

    Uses Claude Opus 4.5 with high effort for comprehensive insights.
    """
    prompt = f"""Analyze this Etsy listing's performance and provide actionable insights:

Listing: {listing.title}
ID: {listing.listing_id}

Performance Metrics (last {listing.period_days} days):
- Views: {listing.views}
- Favorites: {listing.favorites} ({listing.favorite_rate:.2f}%)
- Orders: {listing.orders}
- Conversion Rate: {listing.conversion_rate:.2f}%
- Revenue: ${listing.revenue:.2f}
- Avg Order Value: ${listing.avg_order_value:.2f}

Performance Level: {listing.level.value}

Provide analysis in JSON format:
{{
    "summary": "Brief performance summary",
    "issues": ["List of identified issues"],
    "opportunities": ["Growth opportunities"],
    "recommendations": [
        {{"action": "...", "priority": "high/medium/low", "expected_impact": "..."}}
    ],
    "seo_analysis": {{
        "title_score": 0-100,
        "title_issues": [],
        "keyword_opportunities": []
    }},
    "pricing_analysis": {{
        "current_position": "...",
        "recommendation": "..."
    }}
}}"""

    anthropic = AnthropicClient()
    response = await anthropic.generate(
        prompt=prompt,
        model=AnthropicClient.OPUS,
        effort="high",
        thinking=ThinkingConfig(enabled=True, budget_tokens=20000),
    )

    import json
    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        return {"raw_analysis": response.content}


# === OPTIMIZATION WITH ITERATIVE REFINEMENT ===

async def optimize_underperforming(
    listing_id: str,
    current_content: dict,  # {title, tags, description}
    performance: ListingPerformance,
    max_iterations: int = 5,
    target_score: float = 0.90,
) -> OptimizationResult:
    """
    Optimize underperforming listing using iterative refinement.

    Adapted from ARC-AGI solve_coding.py iteration pattern.
    """
    original_title = current_content.get("title", "")
    original_tags = current_content.get("tags", [])
    original_description = current_content.get("description", "")

    # Initial analysis
    issues = await _identify_issues(current_content, performance)

    # === ITERATIVE REFINEMENT ===

    async def refine_content(
        current: dict,
        task: dict,
        feedback: str,
    ) -> dict:
        """Refine content based on feedback"""
        prompt = f"""Improve this Etsy listing based on the feedback:

Current Title: {current.get('title', '')}
Current Tags: {current.get('tags', [])}
Current Description (first 500 chars): {current.get('description', '')[:500]}

Performance Issues:
{feedback}

Performance Data:
- Conversion Rate: {performance.conversion_rate:.2f}%
- Favorite Rate: {performance.favorite_rate:.2f}%
- Views: {performance.views}

RULES:
- Title: max 140 chars, primary keyword FIRST
- Tags: exactly 13 tags, each max 20 chars
- Description: max 2000 chars, benefits-first

Return JSON:
{{
    "title": "optimized title",
    "tags": ["tag1", "tag2", ...],
    "description": "optimized description"
}}"""

        result = await llm_call(
            prompt,
            model="claude-sonnet-4-5-20250929",
            temperature=0.6,
        )

        import json
        try:
            return json.loads(result.content)
        except json.JSONDecodeError:
            return current

    def score_content(content: dict) -> float:
        """Score content quality"""
        score = 0.5  # Base score

        title = content.get("title", "")
        tags = content.get("tags", [])
        description = content.get("description", "")

        # Title scoring
        if 40 <= len(title) <= 140:
            score += 0.1
        if any(kw.lower() in title.lower() for kw in ["gift", "custom", "personalized"]):
            score += 0.05

        # Tags scoring
        if len(tags) == 13:
            score += 0.1
        valid_tags = sum(1 for t in tags if len(t) <= 20 and " " in t)
        score += (valid_tags / 13) * 0.1

        # Description scoring
        if 500 <= len(description) <= 2000:
            score += 0.1
        if any(cta in description.lower() for cta in ["order now", "add to cart", "shop now"]):
            score += 0.05

        return min(1.0, score)

    # Run iterative refinement
    result = await iterative_refinement(
        initial_output=current_content,
        task={"performance": performance, "issues": issues},
        refine_fn=refine_content,
        score_fn=score_content,
        max_iterations=max_iterations,
        target_score=target_score,
    )

    optimized = result.output

    # Identify improvements made
    improvements = []
    if optimized.get("title") != original_title:
        improvements.append("Title optimized for SEO")
    if optimized.get("tags") != original_tags:
        improvements.append("Tags refreshed with better keywords")
    if optimized.get("description") != original_description:
        improvements.append("Description enhanced with benefits-first approach")

    return OptimizationResult(
        listing_id=listing_id,
        original_title=original_title,
        optimized_title=optimized.get("title", original_title),
        original_tags=original_tags,
        optimized_tags=optimized.get("tags", original_tags),
        original_description=original_description,
        optimized_description=optimized.get("description", original_description),
        issues_found=issues,
        improvements_made=improvements,
        iterations_used=result.iterations_used,
        final_score=result.final_score,
        score_improvement=result.final_score - score_content(current_content),
        total_tokens=result.total_tokens,
    )


async def _identify_issues(content: dict, performance: ListingPerformance) -> list[str]:
    """Identify issues with current listing"""
    issues = []

    title = content.get("title", "")
    tags = content.get("tags", [])
    description = content.get("description", "")

    # Title issues
    if len(title) > 140:
        issues.append(f"Title too long ({len(title)} chars, max 140)")
    if len(title) < 40:
        issues.append("Title too short, missing keywords")

    # Tags issues
    if len(tags) != 13:
        issues.append(f"Wrong tag count ({len(tags)}, should be 13)")
    over_limit = [t for t in tags if len(t) > 20]
    if over_limit:
        issues.append(f"{len(over_limit)} tags over 20-char limit")
    single_word = [t for t in tags if " " not in t]
    if len(single_word) > 3:
        issues.append(f"{len(single_word)} single-word tags (bad for SEO)")

    # Description issues
    if len(description) < 300:
        issues.append("Description too short")
    if len(description) > 2000:
        issues.append("Description too long")

    # Performance issues
    if performance.conversion_rate < 1.0:
        issues.append(f"Low conversion rate ({performance.conversion_rate:.2f}%)")
    if performance.favorite_rate < 5.0:
        issues.append(f"Low favorite rate ({performance.favorite_rate:.2f}%)")

    return issues


# === BATCH OPTIMIZATION ===

async def batch_optimize(
    listings: list[dict],  # [{id, content, performance}, ...]
    max_concurrent: int = 3,
    max_iterations_per_listing: int = 3,
) -> list[OptimizationResult]:
    """
    Optimize multiple listings concurrently.

    Args:
        listings: List of {id, content, performance} dicts
        max_concurrent: Maximum concurrent optimizations
        max_iterations_per_listing: Max refinement iterations per listing

    Returns:
        List of OptimizationResult
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def optimize_one(listing: dict) -> OptimizationResult:
        async with semaphore:
            return await optimize_underperforming(
                listing_id=listing["id"],
                current_content=listing["content"],
                performance=listing["performance"],
                max_iterations=max_iterations_per_listing,
            )

    tasks = [optimize_one(l) for l in listings]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions
    return [r for r in results if isinstance(r, OptimizationResult)]
