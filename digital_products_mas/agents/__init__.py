"""Digital Products MAS Agents"""

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

__all__ = [
    # Content Creator
    "Product",
    "ListingContent",
    "generate_listing_content",
    "optimize_listing",
    # Artisan
    "ArtisanAgent",
    "GeneratedFile",
    "generate_star_map",
    "generate_wall_art",
    "generate_planner",
    # Analytics
    "AnalyticsAgent",
    "ListingPerformance",
    "OptimizationResult",
    "analyze_listing",
    "optimize_underperforming",
]
