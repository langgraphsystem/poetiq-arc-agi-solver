"""
Pytest configuration and fixtures for Digital Products MAS tests.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass


# === PYTEST CONFIG ===

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# === MOCK DATA ===

@pytest.fixture
def sample_product():
    """Sample product for testing"""
    from digital_products_mas.agents.content_creator import Product
    return Product(
        name="Custom Star Map Print",
        description="Personalized star map showing the night sky",
        category="Wall Art",
        keywords=["star map", "custom", "anniversary gift", "wall art"],
        price=29.99,
    )


@pytest.fixture
def sample_performance():
    """Sample performance data for testing"""
    from digital_products_mas.agents.analytics import ListingPerformance
    return ListingPerformance(
        listing_id="123456",
        title="Custom Star Map",
        views=500,
        favorites=25,
        orders=5,
        revenue=149.95,
    )


@pytest.fixture
def sample_order():
    """Sample order for workflow testing"""
    return {
        "order_id": "ORD-TEST-001",
        "customer_id": "CUST-001",
        "products": [
            {
                "sku": "STAR-MAP-001",
                "name": "Custom Star Map",
                "params": {
                    "lat": 40.7128,
                    "lon": -74.0060,
                    "datetime": "2024-01-15 22:00",
                    "title": "The Night We Met",
                }
            }
        ]
    }


# === MOCK CLIENTS ===

@pytest.fixture
def mock_openai():
    """Mock OpenAI client"""
    mock = MagicMock()
    mock.generate = AsyncMock(return_value=("Test response", 100, 50))
    mock.generate_image = AsyncMock(return_value=MagicMock(
        image_bytes=b"fake_image_data",
        revised_prompt=None
    ))
    return mock


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic client"""
    mock = MagicMock()
    mock.generate = AsyncMock(return_value=MagicMock(
        content="Test response",
        thinking=None,
        prompt_tokens=100,
        completion_tokens=50,
    ))
    return mock


@pytest.fixture
def mock_google():
    """Mock Google client"""
    mock = MagicMock()
    mock.generate = AsyncMock(return_value=MagicMock(
        content="Test response",
        prompt_tokens=100,
        completion_tokens=50,
    ))
    mock.generate_tags = AsyncMock(return_value=[
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
    ])
    return mock


# === MOCK LLM ===

@pytest.fixture
def mock_llm_call(monkeypatch):
    """Mock the unified llm_call function"""
    from digital_products_mas.core import ExpertResult

    async def _mock_call(prompt, model, **kwargs):
        return MagicMock(
            content='{"title": "Custom Star Map - Perfect Anniversary Gift"}',
            prompt_tokens=100,
            completion_tokens=50,
            model=model,
            duration_sec=0.5,
        )

    monkeypatch.setattr(
        "digital_products_mas.integrations.unified_llm.llm_call",
        _mock_call
    )


# === UTILITIES ===

@pytest.fixture
def reset_tokens():
    """Reset token tracker before each test"""
    from digital_products_mas.core import reset_session_tokens
    reset_session_tokens()
    yield
    reset_session_tokens()
