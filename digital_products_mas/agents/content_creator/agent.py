"""
Content Creator Agent with Multi-Expert Voting
Adapted from ARC-AGI Solver patterns

This agent generates SEO-optimized content for e-commerce listings
using multiple expert models with voting for best results.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Optional

from digital_products_mas.core.parallel_experts import (
    ExpertConfig,
    ExpertResult,
    ContentType,
    VotingResult,
    solve_with_parallel_experts,
    iterative_refinement,
    get_title_expert_configs,
    get_description_expert_configs,
)
from digital_products_mas.core.rate_limiter import (
    call_with_retry,
    get_model_properties,
    get_session_summary,
)


# === DATA MODELS ===

@dataclass
class Product:
    """Product information for content generation"""
    name: str
    description: str
    category: str
    keywords: list[str]
    price: float = 0.0
    attributes: dict = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


@dataclass
class ListingContent:
    """Generated listing content"""
    titles: list[str]  # Top 3 title options
    tags: list[str]  # Exactly 13 tags
    description: str
    faq: list[dict]  # List of {question, answer}

    # Metadata
    title_votes: dict[str, int] = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0


# === SCORING FUNCTIONS ===

def score_title(title: str, product: Product) -> float:
    """
    Score title quality (0.0 - 1.0)
    Checks: length, keyword presence, format
    """
    score = 1.0

    # Length check (max 140 chars)
    if len(title) > 140:
        score -= 0.3
    elif len(title) < 40:
        score -= 0.1

    # Keyword presence (primary keyword should be first)
    title_lower = title.lower()
    if product.keywords:
        primary_kw = product.keywords[0].lower()
        if primary_kw in title_lower:
            # Bonus if keyword is at the start
            if title_lower.startswith(primary_kw) or title_lower[:30].find(primary_kw) != -1:
                score += 0.1
        else:
            score -= 0.2

    # Check for common SEO patterns
    good_patterns = ["gift for", "handmade", "custom", "personalized", "unique"]
    if any(p in title_lower for p in good_patterns):
        score += 0.05

    return max(0.0, min(1.0, score))


def score_tags(tags: list[str], product: Product) -> float:
    """
    Score tags quality (0.0 - 1.0)
    Checks: count, length limits, uniqueness
    """
    score = 1.0

    # Must have exactly 13 tags
    if len(tags) != 13:
        score -= 0.3

    # Each tag must be <= 20 chars
    over_limit = sum(1 for t in tags if len(t) > 20)
    score -= over_limit * 0.1

    # No single-word tags (Etsy SEO rule)
    single_word = sum(1 for t in tags if " " not in t.strip())
    if single_word > 3:
        score -= 0.1

    # Check uniqueness
    unique_tags = set(t.lower().strip() for t in tags)
    if len(unique_tags) < len(tags):
        score -= 0.1

    # Keyword coverage
    if product.keywords:
        covered = sum(1 for kw in product.keywords[:5] if any(kw.lower() in t.lower() for t in tags))
        score += covered * 0.02

    return max(0.0, min(1.0, score))


def score_description(description: str, product: Product) -> float:
    """
    Score description quality (0.0 - 1.0)
    Checks: length, keyword density, structure
    """
    score = 1.0

    # Length check (optimal: 800-1500 chars)
    length = len(description)
    if length > 2000:
        score -= 0.2
    elif length < 300:
        score -= 0.3
    elif 800 <= length <= 1500:
        score += 0.1

    # Keyword presence
    desc_lower = description.lower()
    if product.keywords:
        found = sum(1 for kw in product.keywords[:5] if kw.lower() in desc_lower)
        score += found * 0.02

    # Structure check (paragraphs, bullet points)
    if "\n\n" in description or "•" in description or "-" in description:
        score += 0.05

    # Call-to-action presence
    cta_patterns = ["order now", "buy now", "add to cart", "shop now", "get yours"]
    if any(p in desc_lower for p in cta_patterns):
        score += 0.05

    return max(0.0, min(1.0, score))


# === LLM CALL WRAPPERS ===

async def _call_openai(
    prompt: str,
    model: str = "gpt-5-mini",
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> tuple[str, int, int]:
    """Call OpenAI API (placeholder - replace with actual implementation)"""
    # In production, use actual OpenAI client
    # This is a placeholder for the pattern
    from openai import AsyncOpenAI

    client = AsyncOpenAI()

    async def _call():
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        usage = response.usage
        return content, usage.prompt_tokens, usage.completion_tokens

    return await _call()


async def _call_anthropic(
    prompt: str,
    model: str = "claude-sonnet-4-5-20250929",
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> tuple[str, int, int]:
    """Call Anthropic API (placeholder)"""
    import anthropic

    client = anthropic.AsyncAnthropic()

    async def _call():
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        usage = response.usage
        return content, usage.input_tokens, usage.output_tokens

    return await _call()


async def _call_gemini(
    prompt: str,
    model: str = "gemini-2.5-flash",
    temperature: float = 0.7,
) -> tuple[str, int, int]:
    """Call Gemini API (placeholder)"""
    import google.generativeai as genai

    async def _call():
        model_instance = genai.GenerativeModel(model)
        response = await model_instance.generate_content_async(
            prompt,
            generation_config={"temperature": temperature}
        )
        # Gemini token counting is approximate
        content = response.text
        prompt_tokens = len(prompt) // 4  # Rough estimate
        completion_tokens = len(content) // 4
        return content, prompt_tokens, completion_tokens

    return await _call()


# === EXPERT SOLVER FUNCTIONS ===

async def solve_title(task: dict, config: ExpertConfig) -> ExpertResult[str]:
    """
    Generate a single title using configured expert.
    This is the solver_fn for parallel_experts.
    """
    product = task["product"]

    # Build prompt based on style
    style_instructions = {
        "creative": "Be creative and catchy. Use power words and emotional hooks.",
        "seo_focused": "Focus on SEO. Put primary keyword FIRST. Include searchable terms.",
        "emotional": "Create emotional connection. Focus on benefits and feelings.",
    }

    prompt = f"""Generate ONE Etsy listing title for this product:

Product: {product.name}
Category: {product.category}
Keywords: {', '.join(product.keywords[:5])}

RULES:
- Maximum 140 characters
- Put primary keyword FIRST in title
- Make it compelling and searchable

Style: {style_instructions.get(config.style, "Be professional and clear.")}

Return ONLY the title, nothing else."""

    start_time = asyncio.get_event_loop().time()

    # Route to appropriate model
    if "gpt" in config.model:
        content, prompt_tokens, completion_tokens = await _call_openai(
            prompt, config.model, config.temperature
        )
    elif "claude" in config.model:
        content, prompt_tokens, completion_tokens = await _call_anthropic(
            prompt, config.model, config.temperature
        )
    else:
        content, prompt_tokens, completion_tokens = await _call_gemini(
            prompt, config.model, config.temperature
        )

    duration = asyncio.get_event_loop().time() - start_time

    # Clean and score
    title = content.strip().strip('"').strip("'")
    score = score_title(title, product)

    return ExpertResult(
        output=title,
        score=score,
        expert_id=config.expert_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=config.model,
        duration_sec=duration,
    )


async def solve_tags(task: dict, config: ExpertConfig) -> ExpertResult[list[str]]:
    """Generate tags using Gemini (best at 20-char limit compliance)"""
    product = task["product"]

    prompt = f"""Generate exactly 13 Etsy tags for this product:

Product: {product.name}
Description: {product.description[:200]}
Category: {product.category}
Keywords: {', '.join(product.keywords[:5])}

CRITICAL RULES:
- Exactly 13 tags
- Each tag MUST be 20 characters or less
- Use multi-word tags (2-3 words) - NO single words
- Include long-tail keywords
- Include occasion keywords (gift for mom, birthday gift, etc.)

Return ONLY a JSON array of 13 strings, nothing else.
Example: ["custom wall art", "gift for her", "home decor"]"""

    start_time = asyncio.get_event_loop().time()

    # Gemini is best for tags due to character limit compliance
    content, prompt_tokens, completion_tokens = await _call_gemini(
        prompt, "gemini-2.5-flash", temperature=0.3
    )

    duration = asyncio.get_event_loop().time() - start_time

    # Parse JSON
    try:
        # Extract JSON array from response
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            tags = json.loads(match.group())
        else:
            tags = json.loads(content)
    except json.JSONDecodeError:
        # Fallback: split by common delimiters
        tags = [t.strip().strip('"').strip("'") for t in content.split(",")]

    # Enforce limits
    tags = [t[:20] for t in tags[:13]]

    score = score_tags(tags, product)

    return ExpertResult(
        output=tags,
        score=score,
        expert_id=config.expert_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model="gemini-2.5-flash",
        duration_sec=duration,
    )


async def solve_description(task: dict, config: ExpertConfig) -> ExpertResult[str]:
    """Generate description using configured expert"""
    product = task["product"]

    style_instructions = {
        "emotional_narrative": """Write in a warm, personal tone.
Focus on how the product makes the buyer FEEL.
Tell a mini-story about using or gifting it.""",
        "benefits_focused": """Lead with BENEFITS, not features.
Use bullet points for key benefits.
Include social proof language.""",
    }

    prompt = f"""Write an Etsy listing description for:

Product: {product.name}
Details: {product.description}
Category: {product.category}
Keywords to include naturally: {', '.join(product.keywords[:5])}

RULES:
- Maximum 2000 characters
- Lead with benefits, not features
- Include emotional hooks
- Add call-to-action at the end
- Natural keyword integration

Style: {style_instructions.get(config.style, "Be professional and compelling.")}

Write the description:"""

    start_time = asyncio.get_event_loop().time()

    if "claude" in config.model:
        content, prompt_tokens, completion_tokens = await _call_anthropic(
            prompt, config.model, config.temperature, max_tokens=2000
        )
    else:
        content, prompt_tokens, completion_tokens = await _call_openai(
            prompt, config.model, config.temperature, max_tokens=2000
        )

    duration = asyncio.get_event_loop().time() - start_time

    description = content.strip()[:2000]
    score = score_description(description, product)

    return ExpertResult(
        output=description,
        score=score,
        expert_id=config.expert_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=config.model,
        duration_sec=duration,
    )


# === MAIN CONTENT GENERATION ===

async def generate_listing_content(
    product: Product,
    num_title_experts: int = 3,
    use_voting: bool = True,
) -> ListingContent:
    """
    Generate complete listing content using multi-expert voting.

    This is the main entry point that orchestrates:
    1. Parallel title generation with voting
    2. Tags generation (Gemini-optimized)
    3. Parallel description generation with voting
    4. FAQ generation

    Args:
        product: Product information
        num_title_experts: Number of title generation experts
        use_voting: Whether to use voting aggregation

    Returns:
        ListingContent with all generated content
    """
    task = {"product": product}

    # === 1. TITLES with parallel experts + voting ===
    title_configs = get_title_expert_configs()[:num_title_experts]

    title_result: VotingResult = await solve_with_parallel_experts(
        task=task,
        expert_configs=title_configs,
        solver_fn=solve_title,
        score_fn=lambda t: score_title(t, product),
        content_type=ContentType.TITLE,
        use_voting=use_voting,
    )

    # Get top 3 unique titles
    titles = []
    seen = set()
    for r in title_result.ranked_results:
        normalized = r.output.lower().strip()
        if normalized not in seen:
            titles.append(r.output)
            seen.add(normalized)
        if len(titles) >= 3:
            break

    # === 2. TAGS (Gemini is best for 20-char compliance) ===
    tags_config = ExpertConfig(
        model="gemini-2.5-flash",
        temperature=0.3,
        expert_id="tags_expert",
    )
    tags_result = await solve_tags(task, tags_config)
    tags = tags_result.output

    # === 3. DESCRIPTION with parallel experts + voting ===
    desc_configs = get_description_expert_configs()

    desc_result: VotingResult = await solve_with_parallel_experts(
        task=task,
        expert_configs=desc_configs,
        solver_fn=solve_description,
        score_fn=lambda d: score_description(d, product),
        content_type=ContentType.DESCRIPTION,
        use_voting=use_voting,
    )

    description = desc_result.best.output if desc_result.best else ""

    # === 4. FAQ (fast generation) ===
    faq = await _generate_faq(product)

    # Calculate totals
    total_tokens = (
        title_result.total_tokens +
        tags_result.total_tokens() +
        desc_result.total_tokens
    )

    return ListingContent(
        titles=titles,
        tags=tags,
        description=description,
        faq=faq,
        title_votes=title_result.vote_counts,
        total_tokens=total_tokens,
    )


async def _generate_faq(product: Product) -> list[dict]:
    """Generate FAQ using fast model"""
    prompt = f"""Generate 5 FAQ items for Etsy listing: {product.name}

Product details: {product.description[:200]}

Return as JSON array: [{{"question": "...", "answer": "..."}}]
Keep answers concise (1-2 sentences each)."""

    try:
        content, _, _ = await _call_openai(
            prompt,
            model="gpt-4.1-nano",  # Fast and cheap
            temperature=0.5,
            max_tokens=1000,
        )

        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(content)
    except Exception:
        return []


# === OPTIMIZATION with ITERATIVE REFINEMENT ===

async def optimize_listing(
    current: ListingContent,
    product: Product,
    performance_data: dict,
    max_iterations: int = 3,
) -> ListingContent:
    """
    Optimize underperforming listing using iterative refinement.
    Adapted from ARC-AGI iterative pattern.

    Args:
        current: Current listing content
        product: Product information
        performance_data: {views, favorites, conversion_rate}
        max_iterations: Max refinement iterations

    Returns:
        Optimized ListingContent
    """

    async def refine_description(desc: str, task: dict, feedback: str) -> str:
        prompt = f"""Improve this Etsy listing description based on feedback:

Current Description:
{desc}

Feedback: {feedback}

Performance Data:
- Views: {performance_data.get('views', 'N/A')}
- Favorites: {performance_data.get('favorites', 'N/A')}
- Conversion: {performance_data.get('conversion_rate', 'N/A')}%

Product: {product.name}
Keywords: {', '.join(product.keywords[:5])}

Write an improved description (max 2000 chars):"""

        content, _, _ = await _call_anthropic(
            prompt,
            model="claude-sonnet-4-5-20250929",
            temperature=0.6,
        )
        return content.strip()[:2000]

    # Refine description
    result = await iterative_refinement(
        initial_output=current.description,
        task={"product": product},
        refine_fn=refine_description,
        score_fn=lambda d: score_description(d, product),
        max_iterations=max_iterations,
        target_score=0.95,
    )

    return ListingContent(
        titles=current.titles,
        tags=current.tags,
        description=result.output,
        faq=current.faq,
        total_tokens=current.total_tokens + result.total_tokens,
    )
