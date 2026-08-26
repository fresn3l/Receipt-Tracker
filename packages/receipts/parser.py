import base64
import json
import re
from pathlib import Path

from openai import OpenAI

from receipts.config import settings
from receipts.schemas import ParsedReceipt

RECEIPT_PROMPT = """You are a grocery receipt parser. Extract structured data from this receipt image.

Return JSON with this exact shape:
{
  "store_name": "store name or null",
  "purchase_date": "YYYY-MM-DD or null",
  "total": 45.67,
  "line_items": [
    {
      "name": "item description as printed",
      "quantity": 1,
      "unit_price": 3.99,
      "line_total": 3.99,
      "category": "Produce",
      "unit_label": "16 oz",
      "unit_amount": 16,
      "normalized_unit": "oz",
      "confidence": 0.95
    }
  ]
}

Categories (pick the best fit): Produce, Dairy, Meat, Seafood, Bakery, Frozen, Beverages, Snacks, Pantry, Household, Personal Care, Other.

Rules:
- Include only actual purchased items, not subtotals, tax, payment lines, or discounts unless they are line items.
- quantity defaults to 1 if not shown.
- unit_price is price per single unit when available; otherwise null.
- line_total is the amount charged for that line.
- purchase_date should be ISO format if visible.
- total is the final amount paid if visible.
- Return valid JSON only.
- category should be one of the listed categories for each line item.
- unit_label is size text from receipt when visible (e.g. 16 oz, 1 gal).
- unit_amount is numeric size (16 for 16 oz).
- normalized_unit is oz, lb, each, L, or null.
- confidence is 0.0-1.0 for how sure you are about that line item."""


def _encode_image(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
    data = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{data}"


def parse_receipt_image(image_path: Path) -> tuple[ParsedReceipt, str]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")

    client = OpenAI(api_key=settings.openai_api_key)
    image_url = _encode_image(image_path)

    response = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": RECEIPT_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        max_tokens=4096,
    )

    raw = response.choices[0].message.content or "{}"
    payload = json.loads(raw)
    return ParsedReceipt.model_validate(payload), raw


def normalize_product_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name.strip())
    return cleaned
