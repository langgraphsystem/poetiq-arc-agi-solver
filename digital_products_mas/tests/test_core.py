"""
Unit tests for core modules.

Tests:
- parallel_experts: voting algorithm, expert configs
- rate_limiter: token tracking, cost estimation
- sandbox: code execution safety
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


class TestParallelExperts:
    """Tests for parallel_experts module"""

    def test_expert_config_creation(self):
        """Test ExpertConfig dataclass"""
        from digital_products_mas.core import ExpertConfig

        config = ExpertConfig(
            model="gpt-5-mini",
            temperature=0.8,
            expert_id="test_expert",
            style="creative",
        )

        assert config.model == "gpt-5-mini"
        assert config.temperature == 0.8
        assert config.expert_id == "test_expert"
        assert config.max_iterations == 1  # default

    def test_expert_result_total_tokens(self):
        """Test ExpertResult token calculation"""
        from digital_products_mas.core import ExpertResult

        result = ExpertResult(
            output="Test output",
            score=0.85,
            expert_id="test",
            prompt_tokens=100,
            completion_tokens=50,
        )

        assert result.total_tokens() == 150

    def test_canonical_key_title(self):
        """Test canonical key generation for titles"""
        from digital_products_mas.core import canonical_key, ContentType

        key1 = canonical_key("Custom Star Map Print", ContentType.TITLE)
        key2 = canonical_key("  CUSTOM STAR MAP PRINT  ", ContentType.TITLE)

        # Should normalize to same key
        assert key1 == key2

    def test_canonical_key_tags(self):
        """Test canonical key generation for tags"""
        from digital_products_mas.core import canonical_key, ContentType

        tags1 = ["star map", "gift", "custom"]
        tags2 = ["custom", "gift", "star map"]

        key1 = canonical_key(tags1, ContentType.TAGS)
        key2 = canonical_key(tags2, ContentType.TAGS)

        # Should produce same key (sorted)
        assert key1 == key2

    def test_get_title_expert_configs(self):
        """Test preset title expert configurations"""
        from digital_products_mas.core import get_title_expert_configs

        configs = get_title_expert_configs()

        assert len(configs) >= 2
        assert all(c.model for c in configs)
        assert any(c.style == "creative" for c in configs)
        assert any(c.style == "seo_focused" for c in configs)

    @pytest.mark.asyncio
    async def test_solve_with_parallel_experts(self):
        """Test parallel expert solving with voting"""
        from digital_products_mas.core import (
            solve_with_parallel_experts,
            ExpertConfig,
            ExpertResult,
            ContentType,
        )

        # Mock solver that returns consistent results
        async def mock_solver(task, config):
            # Expert 1 and 2 return same output (voting)
            if config.expert_id in ["expert_0", "expert_1"]:
                output = "Best Title Option"
            else:
                output = "Different Title"

            return ExpertResult(
                output=output,
                score=0.8 if "Best" in output else 0.6,
                expert_id=config.expert_id,
                prompt_tokens=50,
                completion_tokens=20,
            )

        configs = [
            ExpertConfig(model="test", expert_id=f"expert_{i}")
            for i in range(3)
        ]

        result = await solve_with_parallel_experts(
            task={"test": "data"},
            expert_configs=configs,
            solver_fn=mock_solver,
            score_fn=lambda x: 0.8,
            content_type=ContentType.TITLE,
            use_voting=True,
        )

        # Best Title should be ranked first (2 votes)
        assert result.best.output == "Best Title Option"
        assert len(result.ranked_results) == 3

    @pytest.mark.asyncio
    async def test_iterative_refinement(self):
        """Test iterative refinement loop"""
        from digital_products_mas.core import iterative_refinement

        iteration_count = 0

        async def mock_refine(current, task, feedback):
            nonlocal iteration_count
            iteration_count += 1
            return f"improved_{iteration_count}"

        def mock_score(output):
            # Score increases with iterations
            if "improved" in str(output):
                num = int(output.split("_")[1])
                return min(0.5 + num * 0.2, 1.0)
            return 0.5

        result = await iterative_refinement(
            initial_output="initial",
            task={},
            refine_fn=mock_refine,
            score_fn=mock_score,
            max_iterations=5,
            target_score=0.95,
        )

        assert result.final_score >= 0.9
        assert result.iterations_used <= 5
        assert len(result.improvement_history) > 1


class TestRateLimiter:
    """Tests for rate_limiter module"""

    def test_token_usage_cost(self):
        """Test token usage cost calculation"""
        from digital_products_mas.core import TokenUsage

        usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            model="gpt-5-mini",  # $2/$8 per 1M
        )

        # Expected: (1000/1M * 2) + (500/1M * 8) = 0.002 + 0.004 = 0.006
        assert usage.cost_usd == pytest.approx(0.006, rel=0.01)

    def test_session_tokens_aggregation(self, reset_tokens):
        """Test session token aggregation"""
        from digital_products_mas.core import session_tokens, TokenUsage

        session_tokens.add(TokenUsage(prompt_tokens=100, completion_tokens=50, model="gpt-5-mini"))
        session_tokens.add(TokenUsage(prompt_tokens=200, completion_tokens=100, model="gpt-5-mini"))

        assert session_tokens.total_prompt_tokens == 300
        assert session_tokens.total_completion_tokens == 150
        assert session_tokens.total_tokens == 450

    def test_session_tokens_by_model(self, reset_tokens):
        """Test token breakdown by model"""
        from digital_products_mas.core import session_tokens, TokenUsage

        session_tokens.add(TokenUsage(prompt_tokens=100, completion_tokens=50, model="gpt-5-mini"))
        session_tokens.add(TokenUsage(prompt_tokens=200, completion_tokens=100, model="claude-sonnet-4-5-20250929"))

        by_model = session_tokens.by_model()

        assert "gpt-5-mini" in by_model
        assert "claude-sonnet-4-5-20250929" in by_model
        assert by_model["gpt-5-mini"]["requests"] == 1
        assert by_model["claude-sonnet-4-5-20250929"]["requests"] == 1

    def test_estimate_cost(self):
        """Test cost estimation"""
        from digital_products_mas.core import estimate_cost

        cost = estimate_cost(
            model="claude-sonnet-4-5-20250929",
            prompt_tokens=1000,
            completion_tokens=500,
        )

        # Claude Sonnet: $3/$15 per 1M
        # (1000/1M * 3) + (500/1M * 15) = 0.003 + 0.0075 = 0.0105
        assert cost == pytest.approx(0.0105, rel=0.01)

    def test_estimate_batch_cost(self):
        """Test batch cost estimation"""
        from digital_products_mas.core import estimate_batch_cost

        cost = estimate_batch_cost(
            model="gemini-2.5-flash",
            num_requests=100,
            avg_prompt_tokens=500,
            avg_completion_tokens=100,
        )

        # Should return reasonable estimate
        assert cost > 0
        assert cost < 10  # Gemini Flash is cheap

    def test_get_model_properties(self):
        """Test model-specific properties"""
        from digital_products_mas.core import get_model_properties

        # GPT-5 should have reasoning_effort
        gpt5_props = get_model_properties("gpt-5")
        assert "reasoning_effort" in gpt5_props

        # Claude should have thinking config
        claude_props = get_model_properties("claude-opus-4-5-20251101")
        assert "thinking" in claude_props


class TestSandbox:
    """Tests for sandbox module"""

    @pytest.mark.asyncio
    async def test_run_simple_code(self):
        """Test running simple Python code"""
        from digital_products_mas.core import run_code

        code = """
def main(input_data):
    return {"sum": input_data.get("a", 0) + input_data.get("b", 0)}
"""
        result = await run_code(code, {"a": 5, "b": 3}, timeout_sec=5)

        assert result.success
        assert result.output["sum"] == 8

    @pytest.mark.asyncio
    async def test_run_code_timeout(self):
        """Test code timeout handling"""
        from digital_products_mas.core import run_code

        code = """
import time
def main(input_data):
    time.sleep(10)
    return {}
"""
        result = await run_code(code, {}, timeout_sec=1)

        assert not result.success
        assert result.error == "timeout"

    @pytest.mark.asyncio
    async def test_run_code_error(self):
        """Test code error handling"""
        from digital_products_mas.core import run_code

        code = """
def main(input_data):
    raise ValueError("Test error")
"""
        result = await run_code(code, {}, timeout_sec=5)

        assert not result.success
        assert "ValueError" in result.error or "Test error" in result.error

    def test_validate_code_safety(self):
        """Test code safety validation"""
        from digital_products_mas.core import validate_code_safety

        # Safe code
        safe_code = """
def transform(x):
    return x * 2
"""
        is_safe, error = validate_code_safety(safe_code)
        assert is_safe

        # Unsafe code - subprocess
        unsafe_code = """
import subprocess
subprocess.run(['ls'])
"""
        is_safe, error = validate_code_safety(unsafe_code)
        assert not is_safe
        assert "subprocess" in error.lower()

        # Unsafe code - file access
        unsafe_code2 = """
open('/etc/passwd', 'r')
"""
        is_safe, error = validate_code_safety(unsafe_code2)
        assert not is_safe


class TestVotingAlgorithm:
    """Tests specifically for the ARC-AGI voting algorithm"""

    @pytest.mark.asyncio
    async def test_voting_diversity_first(self):
        """Test that voting prefers diversity"""
        from digital_products_mas.core import (
            solve_with_parallel_experts,
            ExpertConfig,
            ExpertResult,
            ContentType,
        )

        results_by_expert = {
            "e0": "Title A",
            "e1": "Title A",  # Same as e0
            "e2": "Title B",
            "e3": "Title C",
        }

        async def mock_solver(task, config):
            output = results_by_expert.get(config.expert_id, "Unknown")
            return ExpertResult(
                output=output,
                score=0.8,
                expert_id=config.expert_id,
            )

        configs = [
            ExpertConfig(model="test", expert_id=f"e{i}")
            for i in range(4)
        ]

        result = await solve_with_parallel_experts(
            task={},
            expert_configs=configs,
            solver_fn=mock_solver,
            score_fn=lambda x: 0.8,
            content_type=ContentType.TITLE,
            use_voting=True,
        )

        # Title A should be first (2 votes)
        # But we should see diversity in top results
        top_outputs = [r.output for r in result.ranked_results[:3]]
        assert "Title A" in top_outputs
        assert "Title B" in top_outputs or "Title C" in top_outputs
