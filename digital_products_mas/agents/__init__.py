"""Digital Products MAS Agents — All 9 Agents"""

# Core agents (with ARC-AGI patterns)
from .content_creator import (
    Product,
    ListingContent,
    generate_listing_content,
    optimize_listing,
)
from .artisan import (
    ArtisanAgent,
    GeneratedFile,
    generate_star_map,
    generate_wall_art,
    generate_planner,
)
from .analytics import (
    AnalyticsAgent,
    ListingPerformance,
    OptimizationResult,
    analyze_listing,
    optimize_underperforming,
)

# Research agents
from .trend_research import (
    TrendResearchAgent,
    TrendResult,
    discover_trends,
    analyze_trend_potential,
)
from .market_analyst import (
    MarketAnalystAgent,
    CompetitorAnalysis,
    PricingRecommendation,
    analyze_competition,
    recommend_pricing,
)

# Pipeline agents
from .ingestion import (
    IngestionAgent,
    Order,
    ValidationResult,
    validate_order,
    filter_content,
)
from .mockup import (
    MockupAgent,
    MockupResult,
    MockupTemplate,
    create_mockup,
    create_lifestyle_mockup,
)
from .listing_manager import (
    ListingManagerAgent,
    Listing,
    ListingStatus,
    PublishResult,
    publish_to_etsy,
    update_listing,
    sync_inventory,
)
from .fulfillment import (
    FulfillmentAgent,
    FulfillmentOrder,
    FulfillmentStatus,
    FulfillmentResult,
    fulfill_digital,
    fulfill_pod,
    track_shipment,
)

__all__ = [
    # Content Creator (Parallel Expert Voting)
    "Product",
    "ListingContent",
    "generate_listing_content",
    "optimize_listing",
    # Artisan (Sandbox Execution)
    "ArtisanAgent",
    "GeneratedFile",
    "generate_star_map",
    "generate_wall_art",
    "generate_planner",
    # Analytics (Iterative Refinement)
    "AnalyticsAgent",
    "ListingPerformance",
    "OptimizationResult",
    "analyze_listing",
    "optimize_underperforming",
    # Trend Research (Parallel Expert Voting)
    "TrendResearchAgent",
    "TrendResult",
    "discover_trends",
    "analyze_trend_potential",
    # Market Analyst
    "MarketAnalystAgent",
    "CompetitorAnalysis",
    "PricingRecommendation",
    "analyze_competition",
    "recommend_pricing",
    # Ingestion
    "IngestionAgent",
    "Order",
    "ValidationResult",
    "validate_order",
    "filter_content",
    # Mockup
    "MockupAgent",
    "MockupResult",
    "MockupTemplate",
    "create_mockup",
    "create_lifestyle_mockup",
    # Listing Manager
    "ListingManagerAgent",
    "Listing",
    "ListingStatus",
    "PublishResult",
    "publish_to_etsy",
    "update_listing",
    "sync_inventory",
    # Fulfillment
    "FulfillmentAgent",
    "FulfillmentOrder",
    "FulfillmentStatus",
    "FulfillmentResult",
    "fulfill_digital",
    "fulfill_pod",
    "track_shipment",
]
