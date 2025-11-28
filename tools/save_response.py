"""
Save API response to a normalized JSON file.

Usage:
  python tools\save_response.py <document_url> <output_file.json>

This posts to http://127.0.0.1:8000/extract-bill-data and writes a deterministic
JSON file (sorted keys, pages/items sorted) so responses can be compared reliably.
"""

import sys
import json
import requests
from typing import Any, Dict, List


def normalize_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize response structure for deterministic comparison."""
    data = resp.get("data", {})
    pages = data.get("pagewise_line_items", [])

    # Sort pages by page_no
    try:
        pages_sorted = sorted(pages, key=lambda p: int(p.get("page_no", "0")))
    except Exception:
        pages_sorted = sorted(pages, key=lambda p: p.get("page_no", ""))

    for page in pages_sorted:
        items = page.get("bill_items", [])
        # Sort items by item_name
        page["bill_items"] = sorted(items, key=lambda i: i.get("item_name", ""))

    data["pagewise_line_items"] = pages_sorted

    # Build normalized dict with sorted keys
    normalized = {
        "is_success": resp.get("is_success", False),
        "token_usage": resp.get("token_usage", {}),
        "data": data
    }

    return normalized


def main():
    if len(sys.argv) < 3:
        print("Usage: python tools\\save_response.py <document_url> <output_file.json>")
        sys.exit(1)

    document_url = sys.argv[1]
    out_file = sys.argv[2]

    api_url = "http://127.0.0.1:8000/extract-bill-data"

    payload = {"document": document_url}

    print(f"Posting to {api_url}...")
    resp = requests.post(api_url, json=payload, timeout=180)
    try:
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        print(resp.text)
        sys.exit(2)

    result = resp.json()
    normalized = normalize_response(result)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Saved normalized response to {out_file}")


if __name__ == "__main__":
    main()
