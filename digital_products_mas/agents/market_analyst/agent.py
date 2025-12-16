"""
Market Analyst Agent — Competition Analysis and Market Positioning
Uses Gemini 3 Pro for research and Claude for deep analysis.

Features:
- Competitor analysis
- Market positioning
- Pricing optimization
- Gap identification
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Literal

from digital_products_mas.integrations.unified_llm import llm_call


class PricePosition(Enum):
    """Price positioning strategy"""
    BUDGET = "budget"
    VALUE = "value"
    PREMIUM = "premium"
    LUXURY = "luxury"


@dataclass
class CompetitorAnalysis:
    """Analysis of a competitor"""
    name: str
    url: Optional[str] = None
    price_range: tuple[float, float] = (0, 0)
    estimated_sales: int = 0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    unique_features: list[str] = field(default_factory=list)
    review_sentiment: Literal["positive", "mixed", "negative"] = "mixed"


@dataclass
class MarketPosition:
    """Market position analysis"""
    total_competitors: int = 0
    average_price: float = 0.0
    price_range: tuple[float, float] = (0, 0)
    market_saturation: Literal["low", "medium", "high"] = "medium"
    top_competitors: list[CompetitorAnalysis] = field(default_factory=list)
    market_gaps: list[str] = field(default_factory=list)
    differentiation_opportunities: list[str] = field(default_factory=list)


@dataclass
class PricingRecommendation:
    """Pricing recommendation"""
    recommended_price: float
    price_range: tuple[float, float]
    position: PricePosition
    rationale: str
    competitive_prices: list[float] = field(default_factory=list)
    profit_margin_estimate: float = 0.0


class MarketAnalystAgent:
    """
    Market analysis agent.

    Analyzes competition, market positioning, and pricing.
    """

    def __init__(self):
        self.research_model = "gemini-3-pro"
        self.analysis_model = "claude-sonnet-4-5-20250929"

    async def analyze_competitors(
        self,
        product_type: str,
        category: str,
        top_n: int = 10,
    ) -> list[CompetitorAnalysis]:
        """Analyze top competitors"""
        return await analyze_competitors(product_type, category, top_n)

    async def analyze_market(
        self,
        product_type: str,
        category: str,
    ) -> MarketPosition:
        """Analyze market position"""
        return await analyze_market_position(product_type, category)

    async def get_pricing(
        self,
        product_type: str,
        category: str,
        cost: float = 0.0,
        target_margin: float = 0.5,
    ) -> PricingRecommendation:
        """Get pricing recommendation"""
        return await recommend_pricing(product_type, category, cost, target_margin)


# === ANALYSIS FUNCTIONS ===

async def analyze_competitors(
    product_type: str,
    category: str,
    top_n: int = 10,
) -> list[CompetitorAnalysis]:
    """
    Analyze top competitors in a category.

    Uses Gemini 3 Pro for research.
    """
    prompt = f"""Analyze the top {top_n} competitors selling "{product_type}" in the "{category}" category on Etsy.

For each competitor, provide:
1. Shop name
2. Price range (min, max)
3. Estimated monthly sales
4. Key strengths
5. Weaknesses
6. Unique features
7. Review sentiment

Return as JSON array:
[{{
    "name": "Shop Name",
    "price_min": 0.0,
    "price_max": 0.0,
    "estimated_sales": 0,
    "strengths": ["...", "..."],
    "weaknesses": ["...", "..."],
    "unique_features": ["...", "..."],
    "sentiment": "positive|mixed|negative"
}}]"""

    result = await llm_call(
        prompt,
        model="gemini-3-pro",
        temperature=0.3,
    )

    import json
    try:
        data = json.loads(result.content)
        return [
            CompetitorAnalysis(
                name=c["name"],
                price_range=(c.get("price_min", 0), c.get("price_max", 0)),
                estimated_sales=c.get("estimated_sales", 0),
                strengths=c.get("strengths", []),
                weaknesses=c.get("weaknesses", []),
                unique_features=c.get("unique_features", []),
                review_sentiment=c.get("sentiment", "mixed"),
            )
            for c in data[:top_n]
        ]
    except:
        return []


async def analyze_market_position(
    product_type: str,
    category: str,
) -> MarketPosition:
    """
    Analyze market position and opportunities.

    Uses Claude Sonnet for deep analysis.
    """
    # First get competitor data
    competitors = await analyze_competitors(product_type, category, 10)

    # Calculate metrics
    if competitors:
        prices = [c.price_range[0] for c in competitors if c.price_range[0] > 0]
        prices.extend([c.price_range[1] for c in competitors if c.price_range[1] > 0])

        avg_price = sum(prices) / len(prices) if prices else 0
        price_range = (min(prices), max(prices)) if prices else (0, 0)
    else:
        avg_price = 0
        price_range = (0, 0)

    # Deep analysis for gaps and opportunities
    prompt = f"""Analyze the market for "{product_type}" in "{category}":

Top competitors: {[c.name for c in competitors[:5]]}
Average price: ${avg_price:.2f}
Price range: ${price_range[0]:.2f} - ${price_range[1]:.2f}

Identify:
1. Market saturation level (low/medium/high)
2. Top 3 market gaps (unmet needs)
3. Top 3 differentiation opportunities

Return as JSON:
{{
    "saturation": "low|medium|high",
    "gaps": ["gap 1", "gap 2", "gap 3"],
    "opportunities": ["opp 1", "opp 2", "opp 3"]
}}"""

    result = await llm_call(
        prompt,
        model="claude-sonnet-4-5-20250929",
        temperature=0.4,
    )

    import json
    try:
        data = json.loads(result.content)
        saturation = data.get("saturation", "medium")
        gaps = data.get("gaps", [])
        opportunities = data.get("opportunities", [])
    except:
        saturation = "medium"
        gaps = []
        opportunities = []

    return MarketPosition(
        total_competitors=len(competitors),
        average_price=avg_price,
        price_range=price_range,
        market_saturation=saturation,
        top_competitors=competitors[:5],
        market_gaps=gaps,
        differentiation_opportunities=opportunities,
    )


async def recommend_pricing(
    product_type: str,
    category: str,
    cost: float = 0.0,
    target_margin: float = 0.5,
) -> PricingRecommendation:
    """
    Recommend optimal pricing.

    Considers competition, positioning, and target margin.
    """
    # Get market data
    market = await analyze_market_position(product_type, category)

    # Calculate pricing
    min_price = cost / (1 - target_margin) if cost > 0 else market.price_range[0]

    prompt = f"""Recommend pricing for "{product_type}" in "{category}":

Market data:
- Average competitor price: ${market.average_price:.2f}
- Price range: ${market.price_range[0]:.2f} - ${market.price_range[1]:.2f}
- Market saturation: {market.market_saturation}
- My cost: ${cost:.2f}
- Target margin: {target_margin * 100:.0f}%

Recommend:
1. Optimal price point
2. Price range (min, max)
3. Positioning (budget/value/premium/luxury)
4. Rationale (2-3 sentences)

Return as JSON:
{{
    "price": 0.0,
    "min": 0.0,
    "max": 0.0,
    "position": "budget|value|premium|luxury",
    "rationale": "..."
}}"""

    result = await llm_call(
        prompt,
        model="claude-sonnet-4-5-20250929",
        temperature=0.3,
    )

    import json
    try:
        data = json.loads(result.content)

        recommended = max(data.get("price", market.average_price), min_price)
        position = PricePosition(data.get("position", "value"))

        return PricingRecommendation(
            recommended_price=recommended,
            price_range=(data.get("min", market.price_range[0]), data.get("max", market.price_range[1])),
            position=position,
            rationale=data.get("rationale", ""),
            competitive_prices=[c.price_range[0] for c in market.top_competitors if c.price_range[0] > 0],
            profit_margin_estimate=1 - (cost / recommended) if cost > 0 and recommended > 0 else target_margin,
        )
    except:
        return PricingRecommendation(
            recommended_price=market.average_price,
            price_range=market.price_range,
            position=PricePosition.VALUE,
            rationale="Based on market average",
        )
