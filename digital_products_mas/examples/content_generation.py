"""
Example: Content Generation with Multi-Expert Voting

This example demonstrates how to use the Content Creator agent
with parallel experts and voting to generate optimized listing content.

Adapted from ARC-AGI Solver patterns.
"""

import asyncio
import json
from datetime import datetime

# Add parent to path for imports
import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from agents.content_creator import (
    Product,
    generate_listing_content,
    optimize_listing,
)
from core import (
    get_session_summary,
    reset_session_tokens,
    estimate_batch_cost,
)


async def example_basic_generation():
    """
    Basic example: Generate listing content for a product
    """
    print("=" * 60)
    print("EXAMPLE 1: Basic Content Generation with Voting")
    print("=" * 60)

    # Define product
    product = Product(
        name="Custom Star Map Print",
        description="""
        Personalized star map showing the night sky from any location and date.
        Perfect for anniversaries, birthdays, or special moments.
        High-quality print on premium paper.
        """,
        category="Wall Art",
        keywords=[
            "star map",
            "custom star map",
            "anniversary gift",
            "personalized wall art",
            "night sky print",
            "constellation art",
            "gift for her",
            "wedding gift",
        ],
        price=29.99,
    )

    print(f"\nProduct: {product.name}")
    print(f"Category: {product.category}")
    print(f"Keywords: {', '.join(product.keywords[:5])}")

    # Generate content with 3 title experts + voting
    print("\n[Generating content with 3 title experts...]")

    content = await generate_listing_content(
        product=product,
        num_title_experts=3,
        use_voting=True,
    )

    # Display results
    print("\n--- GENERATED TITLES (ranked by votes) ---")
    for i, title in enumerate(content.titles, 1):
        print(f"  {i}. {title}")

    print(f"\n--- TAGS ({len(content.tags)} tags) ---")
    for i, tag in enumerate(content.tags, 1):
        tag_display = f"{tag} ({len(tag)} chars)"
        over = " [OVER LIMIT!]" if len(tag) > 20 else ""
        print(f"  {i:2}. {tag_display}{over}")

    print("\n--- DESCRIPTION ---")
    print(content.description[:500] + "..." if len(content.description) > 500 else content.description)

    print("\n--- FAQ ---")
    for faq in content.faq[:3]:
        print(f"  Q: {faq.get('question', 'N/A')}")
        print(f"  A: {faq.get('answer', 'N/A')[:100]}...")
        print()

    print(f"\n--- STATS ---")
    print(f"Total tokens used: {content.total_tokens}")
    if content.title_votes:
        print(f"Title vote distribution: {content.title_votes}")

    return content


async def example_with_optimization():
    """
    Example: Generate and then optimize underperforming listing
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Iterative Optimization")
    print("=" * 60)

    product = Product(
        name="Minimalist Botanical Wall Art Set",
        description="Set of 3 botanical prints with fern and leaf illustrations",
        category="Wall Art",
        keywords=["botanical art", "plant prints", "minimalist decor", "gallery wall"],
    )

    # Initial generation
    print("\n[Initial generation...]")
    initial = await generate_listing_content(product, num_title_experts=2)

    print(f"Initial description score: ~0.75")
    print(f"Initial description (first 200 chars): {initial.description[:200]}...")

    # Simulate performance data (underperforming)
    performance_data = {
        "views": 150,
        "favorites": 5,
        "conversion_rate": 0.8,  # Low conversion
    }

    # Optimize
    print("\n[Running iterative optimization (max 3 iterations)...]")
    optimized = await optimize_listing(
        current=initial,
        product=product,
        performance_data=performance_data,
        max_iterations=3,
    )

    print(f"\nOptimized description (first 200 chars): {optimized.description[:200]}...")
    print(f"Additional tokens used for optimization: {optimized.total_tokens - initial.total_tokens}")


async def example_batch_estimation():
    """
    Example: Estimate costs for batch processing
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Cost Estimation")
    print("=" * 60)

    # Estimate for 100 products
    num_products = 100

    # Title generation: 3 experts per product
    title_cost = estimate_batch_cost(
        model="gpt-5-mini",
        num_requests=num_products * 3,
        avg_prompt_tokens=500,
        avg_completion_tokens=50,
    )

    # Tags: 1 call per product (Gemini Flash)
    tags_cost = estimate_batch_cost(
        model="gemini-2.5-flash",
        num_requests=num_products,
        avg_prompt_tokens=400,
        avg_completion_tokens=100,
    )

    # Description: 2 experts per product
    desc_cost = estimate_batch_cost(
        model="claude-sonnet-4-5-20250929",
        num_requests=num_products,
        avg_prompt_tokens=800,
        avg_completion_tokens=500,
    ) + estimate_batch_cost(
        model="gpt-5-mini",
        num_requests=num_products,
        avg_prompt_tokens=800,
        avg_completion_tokens=500,
    )

    total_cost = title_cost + tags_cost + desc_cost

    print(f"\nEstimated costs for {num_products} products:")
    print(f"  Titles (3 experts × GPT-5-mini):     ${title_cost:.2f}")
    print(f"  Tags (Gemini 2.5 Flash):             ${tags_cost:.2f}")
    print(f"  Descriptions (Claude + GPT-5-mini): ${desc_cost:.2f}")
    print(f"  ─────────────────────────────────────")
    print(f"  TOTAL:                               ${total_cost:.2f}")
    print(f"  Per product:                         ${total_cost/num_products:.4f}")


async def example_session_tracking():
    """
    Example: Track tokens across a session
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Session Token Tracking")
    print("=" * 60)

    # Reset session
    reset_session_tokens()

    # Generate content for multiple products
    products = [
        Product(
            name="Personalized Pet Portrait",
            description="Custom digital pet portrait from your photo",
            category="Pet Art",
            keywords=["pet portrait", "dog art", "cat art", "custom pet"],
        ),
        Product(
            name="Birth Month Flower Print",
            description="Botanical illustration of birth month flowers",
            category="Wall Art",
            keywords=["birth flower", "birthday gift", "botanical print"],
        ),
    ]

    print(f"\n[Processing {len(products)} products...]")

    for i, product in enumerate(products, 1):
        print(f"\n  Product {i}: {product.name}")
        await generate_listing_content(product, num_title_experts=2)

    # Get session summary
    summary = get_session_summary()

    print("\n--- SESSION SUMMARY ---")
    print(f"Total requests:    {summary['request_count']}")
    print(f"Total tokens:      {summary['total_tokens']:,}")
    print(f"  - Prompt:        {summary['total_prompt_tokens']:,}")
    print(f"  - Completion:    {summary['total_completion_tokens']:,}")
    print(f"Estimated cost:    ${summary['total_cost_usd']:.4f}")

    print("\n--- BY MODEL ---")
    for model, stats in summary.get('by_model', {}).items():
        print(f"  {model}:")
        print(f"    Requests: {stats['requests']}, Tokens: {stats['prompt'] + stats['completion']}, Cost: ${stats['cost']:.4f}")


async def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("DIGITAL PRODUCTS MAS - CONTENT CREATOR EXAMPLES")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Note: These examples require actual API keys to run
    # Set environment variables:
    #   OPENAI_API_KEY
    #   ANTHROPIC_API_KEY
    #   GEMINI_API_KEY

    try:
        await example_basic_generation()
        await example_with_optimization()
        await example_batch_estimation()
        await example_session_tracking()

    except Exception as e:
        print(f"\nError: {e}")
        print("\nNote: Make sure API keys are set in environment variables.")

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
