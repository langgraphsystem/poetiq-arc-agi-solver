# Orchestrator — LangGraph Workflow

## Purpose

Central orchestration of the 9-agent system using **LangGraph**. Manages order processing pipeline from validation to fulfillment.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      LANGGRAPH WORKFLOW                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   START                                                     │
│     │                                                       │
│     ▼                                                       │
│   ┌──────────┐                                             │
│   │ VALIDATE │ ──────────────────────────┐                 │
│   └────┬─────┘                           │                 │
│        │ OK                              │ ERROR           │
│        ▼                                 │                 │
│   ┌──────────┐                           │                 │
│   │ GENERATE │ (Artisan)                 │                 │
│   └────┬─────┘                           │                 │
│        │                                 ▼                 │
│        ▼                           ┌──────────┐           │
│   ┌──────────┐                     │  ERROR   │           │
│   │ CONTENT  │ (Content Creator)   │ HANDLER  │           │
│   └────┬─────┘                     └────┬─────┘           │
│        │                                │                  │
│        ▼                                │                  │
│   ┌──────────┐                          │                  │
│   │  MOCKUP  │                          │                  │
│   └────┬─────┘                          │                  │
│        │                                │                  │
│        ▼                                │                  │
│   ┌──────────┐                          │                  │
│   │ PUBLISH  │                          │                  │
│   └────┬─────┘                          │                  │
│        │                                │                  │
│        ▼                                │                  │
│   ┌──────────┐   POD?                   │                  │
│   │ FULFILL? │ ────┐                    │                  │
│   └────┬─────┘     │                    │                  │
│        │ Digital   │                    │                  │
│        ▼           ▼                    │                  │
│   ┌──────────┐ ┌──────────┐            │                  │
│   │ COMPLETE │ │ FULFILL  │            │                  │
│   └────┬─────┘ └────┬─────┘            │                  │
│        │            │                   │                  │
│        └────────────┴───────────────────┘                  │
│                     │                                      │
│                     ▼                                      │
│                    END                                     │
└─────────────────────────────────────────────────────────────┘
```

## Workflow Nodes

| Node | Agent | Function |
|------|-------|----------|
| `validate` | — | Validate order data, check SKUs |
| `generate` | Artisan | Generate files (star maps, PDFs, etc.) |
| `content` | Content Creator | Generate SEO titles, tags, descriptions |
| `mockup` | Mockup | Create product previews |
| `publish` | Listing Manager | Publish to Etsy/marketplaces |
| `fulfill` | Fulfillment | Send POD orders to printer |
| `complete` | — | Mark order complete |
| `error` | — | Handle failures, flag for review |

## State Management

```python
class WorkflowState(TypedDict):
    # Input
    order_id: str
    order_data: dict

    # Processing
    products: list[dict]
    generated_files: list[dict]  # Annotated for append
    listing_content: list[dict]
    mockups: list[str]

    # Output
    fulfillment_id: Optional[str]
    tracking_number: Optional[str]

    # Control
    errors: list[str]
    requires_human: bool
    current_step: str
    status: str

    # Metrics
    total_tokens: int
    total_cost: float
```

## Usage

```python
from orchestrator import process_order

# Process single order
result = await process_order(
    order_id="ORD-12345",
    order_data={
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
            },
            {
                "sku": "WALL-ART-001",
                "name": "Botanical Print",
                "params": {
                    "prompt": "Fern leaves watercolor",
                    "style": "botanical",
                }
            }
        ]
    }
)

print(f"Status: {result['status']}")
print(f"Generated: {len(result['generated_files'])} files")
print(f"Tokens used: {result['total_tokens']}")
```

## Batch Processing

```python
from orchestrator import process_orders_batch

results = await process_orders_batch(
    orders=[
        {"order_id": "ORD-001", "order_data": {...}},
        {"order_id": "ORD-002", "order_data": {...}},
    ],
    max_concurrent=5,
)
```

## Checkpointing

```python
from langgraph.checkpoint.postgres import PostgresSaver

# Use PostgreSQL for persistent checkpoints
checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)

result = await process_order(
    order_id="ORD-123",
    order_data={...},
    checkpointer=checkpointer,  # State persisted to DB
)
```

## Conditional Routing

```python
def should_fulfill(state) -> Literal["fulfill", "complete"]:
    """Route based on product type"""
    for product in state["products"]:
        # POD products need fulfillment
        if product["sku"].startswith(("SOCK", "MUG", "SHIRT")):
            return "fulfill"
    # Digital products skip fulfillment
    return "complete"
```

## Error Handling

- Errors collected in `state["errors"]`
- `requires_human = True` flags for manual review
- Failed orders route to `error` node
- Error node preserves state for debugging

## Files

```
orchestrator/
├── CLAUDE.md       # This file
├── __init__.py     # Exports
├── state.py        # State definitions
└── graph.py        # LangGraph workflow
    ├── create_workflow()    # Build graph
    ├── compile_workflow()   # Compile with checkpointer
    ├── process_order()      # Single order entry point
    └── process_orders_batch()  # Batch processing
```
