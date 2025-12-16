"""
State definitions for LangGraph workflow.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, Annotated
from operator import add
from enum import Enum


class OrderStatus(Enum):
    """Order processing status"""
    PENDING = "pending"
    VALIDATING = "validating"
    GENERATING = "generating"
    CREATING_CONTENT = "creating_content"
    CREATING_MOCKUPS = "creating_mockups"
    PUBLISHING = "publishing"
    FULFILLING = "fulfilling"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ProductState:
    """State for a single product in the order"""
    sku: str
    name: str
    params: dict = field(default_factory=dict)

    # Generated assets
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    mockup_urls: list[str] = field(default_factory=list)

    # Listing content
    title: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    description: Optional[str] = None

    # Status
    error: Optional[str] = None
    completed: bool = False


@dataclass
class OrderState:
    """Complete order state for workflow"""
    # Input
    order_id: str
    customer_id: Optional[str] = None
    products: list[ProductState] = field(default_factory=list)

    # Processing state
    status: OrderStatus = OrderStatus.PENDING
    current_step: str = "validate"
    errors: list[str] = field(default_factory=list)
    requires_human_review: bool = False

    # Generated outputs
    generated_files: list[dict] = field(default_factory=list)
    listing_content: list[dict] = field(default_factory=list)
    mockups: list[str] = field(default_factory=list)

    # Fulfillment
    fulfillment_id: Optional[str] = None
    tracking_number: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    total_tokens: int = 0
    total_cost: float = 0.0

    def add_error(self, error: str):
        """Add error and update timestamp"""
        self.errors.append(error)
        self.updated_at = datetime.now()

    def update_status(self, status: OrderStatus):
        """Update status and timestamp"""
        self.status = status
        self.updated_at = datetime.now()


# TypedDict version for LangGraph compatibility
from typing import TypedDict


class WorkflowState(TypedDict, total=False):
    """LangGraph-compatible state definition"""
    # Input
    order_id: str
    order_data: dict

    # Validated
    validated_order: Optional[dict]
    products: list[dict]

    # Generated
    generated_files: Annotated[list[dict], add]
    listing_content: Annotated[list[dict], add]
    mockups: Annotated[list[str], add]

    # Fulfillment
    fulfillment_id: Optional[str]
    tracking_number: Optional[str]

    # Control
    errors: Annotated[list[str], add]
    requires_human: bool
    current_step: str
    status: str

    # Metrics
    total_tokens: int
    total_cost: float
