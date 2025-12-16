"""
Ingestion Agent — Order Validation and Content Filtering
Validates orders and filters inappropriate content.

Features:
- Order structure validation
- SKU validation and routing
- Content moderation (blacklist, profanity)
- Customer data validation
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any

from better_profanity import profanity


class ValidationStatus(Enum):
    """Validation result status"""
    VALID = "valid"
    INVALID = "invalid"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ValidationResult:
    """Result of validation"""
    status: ValidationStatus
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_data: Optional[dict] = None


# Valid SKU patterns
VALID_SKU_PATTERNS = [
    r"^STAR-MAP-\d{3}$",
    r"^PLANNER-[A-Z]+-\d{3}$",
    r"^WALL-ART-[A-Z]+-\d{3}$",
    r"^VIDEO-[A-Z]+-\d{3}$",
    r"^SOCK-[A-Z]+-\d{3}$",
    r"^PILLOW-[A-Z]+-\d{3}$",
    r"^MUG-[A-Z]+-\d{3}$",
    r"^NAME-TRACE-\d{3}$",
]

# Blacklisted terms for content
BLACKLIST = [
    # Copyrighted characters
    "mickey mouse", "disney", "marvel", "dc comics",
    "pokemon", "pikachu", "harry potter", "star wars",
    "nintendo", "super mario", "zelda",
    # Trademarked brands
    "nike", "adidas", "gucci", "louis vuitton",
    "coca cola", "pepsi", "starbucks",
    # Restricted content
    "copyright", "trademark", "®", "™",
]


class IngestionAgent:
    """
    Order ingestion and validation agent.

    Validates orders, filters content, and routes to appropriate handlers.
    """

    def __init__(self, custom_blacklist: Optional[list[str]] = None):
        self.blacklist = BLACKLIST + (custom_blacklist or [])
        profanity.load_censor_words()

    async def validate(self, order: dict) -> ValidationResult:
        """
        Validate an incoming order.

        Checks:
        - Required fields
        - SKU validity
        - Content appropriateness
        - Customer data
        """
        return await validate_order(order, self.blacklist)

    async def validate_single_product(self, product: dict) -> ValidationResult:
        """Validate a single product"""
        return await validate_product(product, self.blacklist)


# === VALIDATION FUNCTIONS ===

async def validate_order(
    order: dict,
    blacklist: list[str] = BLACKLIST,
) -> ValidationResult:
    """
    Validate complete order.
    """
    errors = []
    warnings = []
    sanitized = order.copy()

    # Check required fields
    if not order.get("products"):
        errors.append("Order must contain at least one product")
        return ValidationResult(
            status=ValidationStatus.INVALID,
            errors=errors,
        )

    # Validate each product
    sanitized_products = []
    for i, product in enumerate(order.get("products", [])):
        result = await validate_product(product, blacklist)

        if result.status == ValidationStatus.INVALID:
            errors.extend([f"Product {i+1}: {e}" for e in result.errors])
        else:
            warnings.extend([f"Product {i+1}: {w}" for w in result.warnings])
            sanitized_products.append(result.sanitized_data or product)

    sanitized["products"] = sanitized_products

    # Validate customer data if present
    if order.get("customer"):
        customer_result = _validate_customer(order["customer"])
        errors.extend(customer_result.get("errors", []))
        warnings.extend(customer_result.get("warnings", []))

    # Determine final status
    if errors:
        status = ValidationStatus.INVALID
    elif warnings:
        status = ValidationStatus.NEEDS_REVIEW
    else:
        status = ValidationStatus.VALID

    return ValidationResult(
        status=status,
        errors=errors,
        warnings=warnings,
        sanitized_data=sanitized if status != ValidationStatus.INVALID else None,
    )


async def validate_product(
    product: dict,
    blacklist: list[str] = BLACKLIST,
) -> ValidationResult:
    """
    Validate a single product.
    """
    errors = []
    warnings = []
    sanitized = product.copy()

    # Check SKU
    sku = product.get("sku", "")
    if not sku:
        errors.append("Product missing SKU")
    elif not _is_valid_sku(sku):
        errors.append(f"Invalid SKU format: {sku}")

    # Check params
    params = product.get("params", {})
    sanitized_params = params.copy()

    # Validate and sanitize text fields
    text_fields = ["title", "subtitle", "description", "name", "text"]
    for field in text_fields:
        if field in params:
            value = params[field]

            # Check blacklist
            blacklist_result = check_blacklist(value, blacklist)
            if blacklist_result:
                errors.append(f"Blacklisted content in '{field}': {blacklist_result}")

            # Check profanity
            if profanity.contains_profanity(value):
                sanitized_params[field] = profanity.censor(value)
                warnings.append(f"Profanity detected and censored in '{field}'")

    sanitized["params"] = sanitized_params

    # SKU-specific validation
    sku_upper = sku.upper()
    if sku_upper.startswith("STAR-MAP"):
        star_map_errors = _validate_star_map_params(params)
        errors.extend(star_map_errors)
    elif sku_upper.startswith("PLANNER"):
        planner_errors = _validate_planner_params(params)
        errors.extend(planner_errors)

    # Determine status
    if errors:
        status = ValidationStatus.INVALID
    elif warnings:
        status = ValidationStatus.NEEDS_REVIEW
    else:
        status = ValidationStatus.VALID

    return ValidationResult(
        status=status,
        errors=errors,
        warnings=warnings,
        sanitized_data=sanitized if status != ValidationStatus.INVALID else None,
    )


def check_blacklist(text: str, blacklist: list[str] = BLACKLIST) -> Optional[str]:
    """
    Check text against blacklist.

    Returns matched term or None if clean.
    """
    text_lower = text.lower()
    for term in blacklist:
        if term.lower() in text_lower:
            return term
    return None


# === HELPER FUNCTIONS ===

def _is_valid_sku(sku: str) -> bool:
    """Check if SKU matches valid patterns"""
    for pattern in VALID_SKU_PATTERNS:
        if re.match(pattern, sku.upper()):
            return True
    return False


def _validate_customer(customer: dict) -> dict:
    """Validate customer data"""
    errors = []
    warnings = []

    if customer.get("email"):
        email = customer["email"]
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            errors.append("Invalid email format")

    return {"errors": errors, "warnings": warnings}


def _validate_star_map_params(params: dict) -> list[str]:
    """Validate star map specific parameters"""
    errors = []

    # Required: lat, lon, datetime
    if "lat" not in params:
        errors.append("Star map requires 'lat' (latitude)")
    elif not -90 <= params["lat"] <= 90:
        errors.append("Latitude must be between -90 and 90")

    if "lon" not in params:
        errors.append("Star map requires 'lon' (longitude)")
    elif not -180 <= params["lon"] <= 180:
        errors.append("Longitude must be between -180 and 180")

    if "datetime" not in params:
        errors.append("Star map requires 'datetime'")

    return errors


def _validate_planner_params(params: dict) -> list[str]:
    """Validate planner specific parameters"""
    errors = []

    valid_templates = ["daily", "weekly", "monthly", "budget", "habit"]
    if params.get("template") and params["template"] not in valid_templates:
        errors.append(f"Invalid planner template. Valid: {valid_templates}")

    valid_sizes = ["Letter", "A4", "A5"]
    if params.get("size") and params["size"] not in valid_sizes:
        errors.append(f"Invalid planner size. Valid: {valid_sizes}")

    return errors
