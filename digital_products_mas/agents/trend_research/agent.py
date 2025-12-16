"""
Trend Research Agent — Discover Trending Products and Niches
Uses Gemini 3 Pro for web grounding and multi-source research.

Features:
- Multi-source trend discovery (Google Trends, Pinterest, Etsy)
- Parallel expert analysis with voting
- Niche opportunity scoring
- Seasonal trend prediction
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Literal

from digital_products_mas.core.parallel_experts import (
    solve_with_parallel_experts,
    ExpertConfig,
    ExpertResult,
    ContentType,
)
from digital_products_mas.integrations.unified_llm import llm_call, best_for_task


class TrendSource(Enum):
    """Sources for trend research"""
    GOOGLE_TRENDS = "google_trends"
    PINTEREST = "pinterest"
    ETSY = "etsy"
    AMAZON = "amazon"
    SOCIAL_MEDIA = "social_media"


class TrendStrength(Enum):
    """Trend strength classification"""
    EMERGING = "emerging"      # Just starting
    GROWING = "growing"        # Steady growth
    PEAK = "peak"              # At maximum
    DECLINING = "declining"    # Past peak
    STABLE = "stable"          # Consistent demand


@dataclass
class TrendData:
    """Data about a discovered trend"""
    keyword: str
    category: str
    strength: TrendStrength
    search_volume: int = 0
    growth_rate: float = 0.0  # Percentage
    competition_level: Literal["low", "medium", "high"] = "medium"
    seasonality: Optional[str] = None  # e.g., "Q4", "Summer"
    sources: list[TrendSource] = field(default_factory=list)
    related_keywords: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1

    @property
    def opportunity_score(self) -> float:
        """Calculate opportunity score based on metrics"""
        score = 0.5

        # Growth rate bonus
        if self.growth_rate > 50:
            score += 0.2
        elif self.growth_rate > 20:
            score += 0.1

        # Competition penalty
        if self.competition_level == "high":
            score -= 0.15
        elif self.competition_level == "low":
            score += 0.15

        # Strength bonus
        if self.strength == TrendStrength.EMERGING:
            score += 0.2
        elif self.strength == TrendStrength.GROWING:
            score += 0.1

        # Multiple sources bonus
        if len(self.sources) >= 3:
            score += 0.1

        return min(1.0, max(0.0, score))


@dataclass
class NicheOpportunity:
    """Analysis of a niche opportunity"""
    niche: str
    trends: list[TrendData]
    market_size: Literal["small", "medium", "large"] = "medium"
    profit_potential: Literal["low", "medium", "high"] = "medium"
    entry_difficulty: Literal["easy", "medium", "hard"] = "medium"
    recommended_products: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    overall_score: float = 0.0


class TrendResearchAgent:
    """
    Trend research agent using multi-source analysis.

    Uses Gemini 3 Pro for web grounding and research,
    with parallel expert voting for consensus.
    """

    def __init__(self):
        self.default_model = "gemini-3-pro"

    async def research(
        self,
        category: str,
        num_trends: int = 10,
        use_voting: bool = True,
    ) -> list[TrendData]:
        """
        Research trends in a category.

        Uses parallel experts to research from multiple angles,
        then votes on the most promising trends.
        """
        return await research_trends(
            category=category,
            num_trends=num_trends,
            use_voting=use_voting,
        )

    async def analyze_niche(
        self,
        niche: str,
    ) -> NicheOpportunity:
        """Analyze a specific niche opportunity"""
        return await analyze_niche(niche)

    async def get_keywords(
        self,
        seed_keyword: str,
        count: int = 20,
    ) -> list[str]:
        """Get related trending keywords"""
        return await get_trending_keywords(seed_keyword, count)


# === RESEARCH FUNCTIONS ===

async def research_trends(
    category: str,
    num_trends: int = 10,
    use_voting: bool = True,
) -> list[TrendData]:
    """
    Research trends using parallel experts with voting.

    Each expert focuses on different sources/angles,
    results are aggregated through voting.
    """
    expert_configs = [
        ExpertConfig(
            model="gemini-3-pro",
            temperature=0.5,
            expert_id="google_trends",
            style="search_focused",
        ),
        ExpertConfig(
            model="gemini-3-pro",
            temperature=0.6,
            expert_id="social_media",
            style="viral_focused",
        ),
        ExpertConfig(
            model="gemini-3-pro",
            temperature=0.4,
            expert_id="marketplace",
            style="sales_focused",
        ),
    ]

    async def research_expert(task: dict, config: ExpertConfig) -> ExpertResult:
        """Single expert researches trends"""
        prompt = f"""Research trending products in the "{task['category']}" category.

Focus: {config.style.replace('_', ' ')}
Expert perspective: {config.expert_id.replace('_', ' ')}

Find {task['num_trends']} trending products/keywords with:
1. Current search volume trend
2. Growth rate (emerging, growing, peak, declining)
3. Competition level
4. Seasonality if any
5. Related keywords

Return as JSON array:
[{{
    "keyword": "...",
    "strength": "emerging|growing|peak|declining|stable",
    "growth_rate": 0-100,
    "competition": "low|medium|high",
    "seasonality": null or "Q4", "Summer", etc.,
    "related": ["kw1", "kw2"],
    "confidence": 0.0-1.0
}}]"""

        result = await llm_call(
            prompt,
            model=config.model,
            temperature=config.temperature,
        )

        import json
        try:
            trends_raw = json.loads(result.content)
            trends = [
                TrendData(
                    keyword=t["keyword"],
                    category=task["category"],
                    strength=TrendStrength(t.get("strength", "stable")),
                    growth_rate=t.get("growth_rate", 0),
                    competition_level=t.get("competition", "medium"),
                    seasonality=t.get("seasonality"),
                    related_keywords=t.get("related", []),
                    confidence=t.get("confidence", 0.5),
                    sources=[TrendSource(config.expert_id)] if config.expert_id in [s.value for s in TrendSource] else [],
                )
                for t in trends_raw
            ]
            score = sum(t.opportunity_score for t in trends) / len(trends) if trends else 0
        except:
            trends = []
            score = 0

        return ExpertResult(
            output=trends,
            score=score,
            expert_id=config.expert_id,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )

    task = {"category": category, "num_trends": num_trends}

    if use_voting:
        result = await solve_with_parallel_experts(
            task=task,
            expert_configs=expert_configs,
            solver_fn=research_expert,
            score_fn=lambda trends: sum(t.opportunity_score for t in trends) / len(trends) if trends else 0,
            content_type=ContentType.DESCRIPTION,  # Reusing for complex output
            use_voting=True,
        )

        # Merge trends from all experts
        all_trends = {}
        for expert_result in result.ranked_results:
            for trend in expert_result.output:
                key = trend.keyword.lower()
                if key in all_trends:
                    # Merge sources
                    all_trends[key].sources.extend(trend.sources)
                    all_trends[key].confidence = max(all_trends[key].confidence, trend.confidence)
                else:
                    all_trends[key] = trend

        # Sort by opportunity score
        trends = sorted(all_trends.values(), key=lambda t: t.opportunity_score, reverse=True)
        return trends[:num_trends]

    else:
        # Single expert
        expert_result = await research_expert(task, expert_configs[0])
        return expert_result.output[:num_trends]


async def analyze_niche(niche: str) -> NicheOpportunity:
    """
    Deep analysis of a specific niche.

    Uses Claude Opus 4.5 with high effort for comprehensive analysis.
    """
    prompt = f"""Analyze the "{niche}" niche for digital products and POD items.

Provide comprehensive analysis:

1. Market Size: small/medium/large
2. Profit Potential: low/medium/high
3. Entry Difficulty: easy/medium/hard
4. Top 5 trending products/keywords in this niche
5. Recommended product types to create
6. Key risks and challenges

Return as JSON:
{{
    "market_size": "small|medium|large",
    "profit_potential": "low|medium|high",
    "entry_difficulty": "easy|medium|hard",
    "trends": [
        {{"keyword": "...", "growth_rate": 0-100, "competition": "low|medium|high"}}
    ],
    "recommended_products": ["product type 1", "product type 2"],
    "risks": ["risk 1", "risk 2"],
    "overall_score": 0.0-1.0
}}"""

    from digital_products_mas.integrations.anthropic_client import AnthropicClient, ThinkingConfig

    anthropic = AnthropicClient()
    response = await anthropic.generate(
        prompt=prompt,
        model=AnthropicClient.OPUS,
        effort="high",
        thinking=ThinkingConfig(enabled=True, budget_tokens=15000),
    )

    import json
    try:
        data = json.loads(response.content)

        trends = [
            TrendData(
                keyword=t["keyword"],
                category=niche,
                strength=TrendStrength.GROWING,
                growth_rate=t.get("growth_rate", 0),
                competition_level=t.get("competition", "medium"),
            )
            for t in data.get("trends", [])
        ]

        return NicheOpportunity(
            niche=niche,
            trends=trends,
            market_size=data.get("market_size", "medium"),
            profit_potential=data.get("profit_potential", "medium"),
            entry_difficulty=data.get("entry_difficulty", "medium"),
            recommended_products=data.get("recommended_products", []),
            risks=data.get("risks", []),
            overall_score=data.get("overall_score", 0.5),
        )
    except:
        return NicheOpportunity(niche=niche, trends=[])


async def get_trending_keywords(
    seed_keyword: str,
    count: int = 20,
) -> list[str]:
    """
    Get trending related keywords.

    Uses Gemini 2.5 Flash for fast keyword expansion.
    """
    prompt = f"""Generate {count} trending long-tail keywords related to "{seed_keyword}".

Focus on:
- Etsy search terms
- Gift-giving occasions
- Personalization options
- Seasonal variations

Return ONLY a JSON array of strings:
["keyword 1", "keyword 2", ...]"""

    result = await llm_call(
        prompt,
        model="gemini-2.5-flash",
        temperature=0.5,
    )

    import json
    try:
        keywords = json.loads(result.content)
        return keywords[:count]
    except:
        return []
