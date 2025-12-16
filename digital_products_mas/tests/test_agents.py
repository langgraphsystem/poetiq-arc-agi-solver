"""
Integration tests for agents.

Tests:
- Content Creator: title/tag/description generation
- Artisan: file generation
- Analytics: performance analysis and optimization
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestContentCreator:
    """Tests for Content Creator agent"""

    def test_product_creation(self, sample_product):
        """Test Product dataclass"""
        assert sample_product.name == "Custom Star Map Print"
        assert len(sample_product.keywords) >= 4
        assert sample_product.price == 29.99

    def test_score_title_valid(self, sample_product):
        """Test title scoring with valid title"""
        from digital_products_mas.agents.content_creator.agent import score_title

        # Good title: keyword first, right length
        title = "Star Map Custom Print - Perfect Anniversary Gift for Her"
        score = score_title(title, sample_product)

        assert 0.7 <= score <= 1.0

    def test_score_title_too_long(self, sample_product):
        """Test title scoring with too long title"""
        from digital_products_mas.agents.content_creator.agent import score_title

        title = "A" * 150  # Over 140 chars
        score = score_title(title, sample_product)

        assert score < 0.8  # Penalty applied

    def test_score_tags_valid(self, sample_product):
        """Test tag scoring with valid tags"""
        from digital_products_mas.agents.content_creator.agent import score_tags

        tags = [
            "custom star map",
            "anniversary gift",
            "personalized art",
            "night sky print",
            "wedding gift",
            "wall decor",
            "gift for her",
            "gift for him",
            "romantic gift",
            "celestial art",
            "constellation",
            "unique gift",
            "home decor",
        ]

        score = score_tags(tags, sample_product)
        assert score >= 0.8  # 13 tags, all valid

    def test_score_tags_wrong_count(self, sample_product):
        """Test tag scoring with wrong tag count"""
        from digital_products_mas.agents.content_creator.agent import score_tags

        tags = ["tag1", "tag2", "tag3"]  # Only 3 tags
        score = score_tags(tags, sample_product)

        assert score < 0.8  # Penalty for wrong count

    def test_score_tags_over_limit(self, sample_product):
        """Test tag scoring with tags over 20 chars"""
        from digital_products_mas.agents.content_creator.agent import score_tags

        tags = [
            "this tag is way too long for etsy",  # Over 20 chars
            "another very long tag here",
        ] + ["short tag"] * 11

        score = score_tags(tags, sample_product)
        assert score < 0.8  # Penalty for over-limit tags

    def test_score_description_valid(self, sample_product):
        """Test description scoring"""
        from digital_products_mas.agents.content_creator.agent import score_description

        description = """
        Create unforgettable memories with our Custom Star Map Print!

        This beautiful personalized wall art captures the exact night sky
        from any special moment - your wedding night, first date, or
        the birth of your child.

        Features:
        • Astronomically accurate star positions
        • High-quality 300 DPI print
        • Choice of sizes and frames
        • Perfect gift for anniversaries

        Order now and preserve your special moment forever!
        """

        score = score_description(description, sample_product)
        assert score >= 0.7


class TestArtisan:
    """Tests for Artisan agent"""

    def test_detect_product_type(self):
        """Test SKU pattern detection"""
        from digital_products_mas.agents.artisan.agent import ArtisanAgent, ProductType

        agent = ArtisanAgent()

        assert agent.detect_product_type("STAR-MAP-001") == ProductType.STAR_MAP
        assert agent.detect_product_type("PLANNER-DAILY-001") == ProductType.PLANNER
        assert agent.detect_product_type("WALL-ART-BOTANICAL") == ProductType.WALL_ART
        assert agent.detect_product_type("VIDEO-PROMO-001") == ProductType.VIDEO_PROMO
        assert agent.detect_product_type("UNKNOWN-SKU") is None

    def test_generated_file_properties(self):
        """Test GeneratedFile dataclass"""
        from digital_products_mas.agents.artisan import GeneratedFile

        file = GeneratedFile(
            path="test.png",
            file_bytes=b"x" * 1024,  # 1KB
            metadata={"format": "png"},
        )

        assert file.size_kb == 1.0
        assert len(file.checksum) == 32  # MD5 hash
        assert file.metadata["format"] == "png"

    @pytest.mark.asyncio
    async def test_generate_star_map(self):
        """Test star map generation (sandbox)"""
        from digital_products_mas.agents.artisan import generate_star_map

        # This will run actual code in sandbox
        file = await generate_star_map(
            lat=40.7128,
            lon=-74.0060,
            datetime_str="2024-01-15 22:00",
            title="The Night We Met",
            subtitle="New York City",
        )

        assert file.path.endswith(".png")
        assert file.size_kb > 10  # Should be substantial
        assert file.metadata["lat"] == 40.7128

    @pytest.mark.asyncio
    async def test_generate_planner(self):
        """Test PDF planner generation (sandbox)"""
        from digital_products_mas.agents.artisan import generate_planner

        file = await generate_planner(
            template="daily",
            title="My Daily Planner",
            size="Letter",
        )

        assert file.path.endswith(".pdf")
        assert file.size_kb > 1
        assert file.metadata["template"] == "daily"


class TestAnalytics:
    """Tests for Analytics agent"""

    def test_listing_performance_classification(self):
        """Test performance level classification"""
        from digital_products_mas.agents.analytics import ListingPerformance, PerformanceLevel

        # Excellent (3%+ conversion)
        excellent = ListingPerformance(
            listing_id="1",
            title="Test",
            views=100,
            orders=4,
            revenue=100,
        )
        assert excellent.level == PerformanceLevel.EXCELLENT

        # Poor (0.5-1% conversion)
        poor = ListingPerformance(
            listing_id="2",
            title="Test",
            views=200,
            orders=1,
            revenue=25,
        )
        assert poor.level == PerformanceLevel.POOR
        assert poor.needs_optimization

    def test_optimization_result(self):
        """Test OptimizationResult dataclass"""
        from digital_products_mas.agents.analytics import OptimizationResult

        result = OptimizationResult(
            listing_id="123",
            original_title="Old Title",
            optimized_title="New SEO Title",
            original_tags=["old", "tags"],
            optimized_tags=["new", "better", "tags"],
            original_description="Short",
            optimized_description="Much better description with benefits",
            issues_found=["Title too short"],
            improvements_made=["Title optimized"],
            iterations_used=3,
            final_score=0.92,
            score_improvement=0.22,
        )

        assert result.final_score > result.score_improvement
        assert len(result.improvements_made) > 0

    @pytest.mark.asyncio
    async def test_identify_issues(self, sample_performance):
        """Test issue identification"""
        from digital_products_mas.agents.analytics.agent import _identify_issues

        content = {
            "title": "Short",  # Too short
            "tags": ["single"],  # Wrong count, single word
            "description": "Brief",  # Too short
        }

        issues = await _identify_issues(content, sample_performance)

        assert len(issues) > 0
        assert any("title" in i.lower() or "short" in i.lower() for i in issues)
        assert any("tag" in i.lower() for i in issues)


class TestAgentIntegration:
    """Integration tests across agents"""

    @pytest.mark.asyncio
    async def test_content_to_analytics_flow(self, sample_product):
        """Test flow from content creation to analytics optimization"""
        from digital_products_mas.agents.analytics import ListingPerformance

        # Simulate poor-performing listing
        performance = ListingPerformance(
            listing_id="test-123",
            title=sample_product.name,
            views=1000,
            favorites=20,
            orders=3,  # 0.3% conversion - Critical
            revenue=89.97,
        )

        assert performance.needs_optimization
        assert performance.conversion_rate == pytest.approx(0.3, rel=0.1)
