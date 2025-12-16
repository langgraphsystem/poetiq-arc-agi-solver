"""
LangGraph Workflow for Digital Products MAS

Orchestrates the complete order processing pipeline:
1. Validate order
2. Generate files (Artisan)
3. Create content (Content Creator)
4. Create mockups
5. Publish listings
6. Fulfill order
"""

import asyncio
from typing import Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import WorkflowState

# Import agents (lazy to avoid circular imports)
def get_artisan():
    from digital_products_mas.agents.artisan import ArtisanAgent
    return ArtisanAgent()

def get_content_creator():
    from digital_products_mas.agents.content_creator import (
        Product, generate_listing_content
    )
    return Product, generate_listing_content

def get_analytics():
    from digital_products_mas.agents.analytics import AnalyticsAgent
    return AnalyticsAgent()


# === NODE FUNCTIONS ===

async def validate_order(state: WorkflowState) -> WorkflowState:
    """
    Node 1: Validate incoming order.

    Checks:
    - Required fields present
    - SKU patterns valid
    - Customer data valid
    """
    order_data = state.get("order_data", {})

    # Basic validation
    errors = []

    if not order_data.get("products"):
        errors.append("No products in order")

    products = []
    for p in order_data.get("products", []):
        if not p.get("sku"):
            errors.append(f"Product missing SKU: {p}")
            continue

        products.append({
            "sku": p["sku"],
            "name": p.get("name", ""),
            "params": p.get("params", {}),
        })

    if errors:
        return {
            **state,
            "errors": errors,
            "requires_human": True,
            "current_step": "error",
            "status": "failed",
        }

    return {
        **state,
        "validated_order": order_data,
        "products": products,
        "current_step": "generate",
        "status": "validated",
    }


async def generate_files(state: WorkflowState) -> WorkflowState:
    """
    Node 2: Generate product files using Artisan agent.
    """
    products = state.get("products", [])
    artisan = get_artisan()

    generated = []
    errors = []

    for product in products:
        try:
            file = await artisan.generate(
                sku=product["sku"],
                params=product["params"],
            )

            generated.append({
                "sku": product["sku"],
                "path": file.path,
                "size_kb": file.size_kb,
                "metadata": file.metadata,
            })

        except Exception as e:
            errors.append(f"Failed to generate {product['sku']}: {e}")

    return {
        **state,
        "generated_files": generated,
        "errors": errors,
        "current_step": "content" if not errors else "error",
        "status": "files_generated",
    }


async def create_content(state: WorkflowState) -> WorkflowState:
    """
    Node 3: Create listing content using Content Creator agent.
    """
    products = state.get("products", [])
    generated_files = state.get("generated_files", [])

    Product, generate_listing_content = get_content_creator()

    content_list = []
    total_tokens = 0

    for product in products:
        # Create Product object
        p = Product(
            name=product["name"],
            description=product["params"].get("description", ""),
            category=product["params"].get("category", "Digital Products"),
            keywords=product["params"].get("keywords", []),
        )

        # Generate content with voting
        content = await generate_listing_content(
            product=p,
            num_title_experts=3,
            use_voting=True,
        )

        content_list.append({
            "sku": product["sku"],
            "titles": content.titles,
            "tags": content.tags,
            "description": content.description,
            "faq": content.faq,
        })

        total_tokens += content.total_tokens

    return {
        **state,
        "listing_content": content_list,
        "total_tokens": state.get("total_tokens", 0) + total_tokens,
        "current_step": "mockup",
        "status": "content_created",
    }


async def create_mockups(state: WorkflowState) -> WorkflowState:
    """
    Node 4: Create product mockups.

    Placeholder - would integrate with mockup service.
    """
    generated_files = state.get("generated_files", [])

    mockups = []
    for file in generated_files:
        # Placeholder mockup URLs
        mockups.append(f"https://mockups.example.com/{file['sku']}/preview.jpg")

    return {
        **state,
        "mockups": mockups,
        "current_step": "publish",
        "status": "mockups_created",
    }


async def publish_listings(state: WorkflowState) -> WorkflowState:
    """
    Node 5: Publish to marketplace.

    Placeholder - would integrate with Etsy/other APIs.
    """
    # Placeholder - in production would call Etsy API
    return {
        **state,
        "current_step": "fulfill",
        "status": "published",
    }


async def fulfill_order(state: WorkflowState) -> WorkflowState:
    """
    Node 6: Send to fulfillment (for POD products).

    Placeholder - would integrate with Printify/Printful.
    """
    # Placeholder fulfillment
    return {
        **state,
        "fulfillment_id": f"FUL-{state['order_id']}",
        "current_step": "complete",
        "status": "fulfilled",
    }


async def handle_error(state: WorkflowState) -> WorkflowState:
    """
    Error handling node.
    """
    return {
        **state,
        "requires_human": True,
        "status": "needs_review",
    }


async def complete_order(state: WorkflowState) -> WorkflowState:
    """
    Final node - mark order complete.
    """
    return {
        **state,
        "status": "completed",
        "current_step": "done",
    }


# === ROUTING ===

def route_after_validate(state: WorkflowState) -> Literal["generate", "error"]:
    """Route after validation"""
    if state.get("errors"):
        return "error"
    return "generate"


def route_after_generate(state: WorkflowState) -> Literal["content", "error"]:
    """Route after file generation"""
    if state.get("errors"):
        return "error"
    return "content"


def should_fulfill(state: WorkflowState) -> Literal["fulfill", "complete"]:
    """Check if order needs fulfillment (POD) or is digital-only"""
    # Check if any product is POD
    products = state.get("products", [])
    for p in products:
        if p["sku"].startswith(("SOCK", "PILLOW", "MUG", "SHIRT")):
            return "fulfill"
    return "complete"


# === BUILD GRAPH ===

def create_workflow() -> StateGraph:
    """
    Create the LangGraph workflow.

    Flow:
    validate → generate → content → mockup → publish → fulfill? → complete
                 ↓           ↓
                error ←──────┘
    """
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("validate", validate_order)
    workflow.add_node("generate", generate_files)
    workflow.add_node("content", create_content)
    workflow.add_node("mockup", create_mockups)
    workflow.add_node("publish", publish_listings)
    workflow.add_node("fulfill", fulfill_order)
    workflow.add_node("complete", complete_order)
    workflow.add_node("error", handle_error)

    # Set entry point
    workflow.set_entry_point("validate")

    # Add edges
    workflow.add_conditional_edges("validate", route_after_validate)
    workflow.add_conditional_edges("generate", route_after_generate)
    workflow.add_edge("content", "mockup")
    workflow.add_edge("mockup", "publish")
    workflow.add_conditional_edges("publish", should_fulfill)
    workflow.add_edge("fulfill", "complete")
    workflow.add_edge("complete", END)
    workflow.add_edge("error", END)

    return workflow


def compile_workflow(checkpointer=None):
    """Compile workflow with optional checkpointer"""
    workflow = create_workflow()

    if checkpointer is None:
        checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


# === ENTRY POINT ===

async def process_order(
    order_id: str,
    order_data: dict,
    checkpointer=None,
) -> WorkflowState:
    """
    Process a single order through the workflow.

    Args:
        order_id: Unique order identifier
        order_data: Order details including products
        checkpointer: Optional LangGraph checkpointer

    Returns:
        Final workflow state
    """
    app = compile_workflow(checkpointer)

    config = {"configurable": {"thread_id": order_id}}

    initial_state: WorkflowState = {
        "order_id": order_id,
        "order_data": order_data,
        "generated_files": [],
        "listing_content": [],
        "mockups": [],
        "errors": [],
        "requires_human": False,
        "current_step": "validate",
        "status": "pending",
        "total_tokens": 0,
        "total_cost": 0.0,
    }

    result = await app.ainvoke(initial_state, config)

    return result


# === BATCH PROCESSING ===

async def process_orders_batch(
    orders: list[dict],  # [{order_id, order_data}, ...]
    max_concurrent: int = 5,
) -> list[WorkflowState]:
    """
    Process multiple orders concurrently.

    Args:
        orders: List of order dicts
        max_concurrent: Maximum concurrent orders

    Returns:
        List of final states
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_one(order: dict) -> WorkflowState:
        async with semaphore:
            return await process_order(
                order_id=order["order_id"],
                order_data=order["order_data"],
            )

    tasks = [process_one(o) for o in orders]
    return await asyncio.gather(*tasks)
