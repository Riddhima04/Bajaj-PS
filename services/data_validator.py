"""
Data Validator - Validates and deduplicates extracted bill data
"""

import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates and deduplicates extracted bill data"""
    
    def __init__(self):
        self.similarity_threshold = 0.8  # Threshold for considering items as duplicates
    
    def validate_and_deduplicate(
        self, 
        pagewise_line_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate and deduplicate line items across pages
        
        Args:
            pagewise_line_items: List of page data with bill items
            
        Returns:
            Validated and deduplicated pagewise line items
        """
        if not pagewise_line_items:
            return []
        
        # First, validate each page's data
        validated_pages = []
        for page in pagewise_line_items:
            validated_page = self._validate_page(page)
            validated_pages.append(validated_page)
        
        # Deduplicate items across pages
        deduplicated_pages = self._deduplicate_items(validated_pages)
        
        return deduplicated_pages
    
    def _validate_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single page's data"""
        validated_page = {
            "page_no": str(page.get("page_no", "1")),
            "page_type": self._normalize_page_type(page.get("page_type", "Bill Detail")),
            "bill_items": []
        }
        
        bill_items = page.get("bill_items", [])
        
        for item in bill_items:
            validated_item = self._validate_item(item)
            if validated_item:
                validated_page["bill_items"].append(validated_item)
        
        return validated_page
    
    def _validate_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate a single line item"""
        # Check if item has required fields
        item_name = str(item.get("item_name", "")).strip()
        
        # Skip items with empty names (likely not real items)
        if not item_name or len(item_name) < 2:
            return None
        
        # Skip items that look like totals/subtotals
        if self._is_total_or_subtotal(item_name):
            return None
        
        # Validate and convert numeric fields
        try:
            item_amount = float(item.get("item_amount", 0.0))
            item_rate = float(item.get("item_rate", 0.0))
            item_quantity = float(item.get("item_quantity", 0.0))
        except (ValueError, TypeError):
            logger.warning(f"Invalid numeric values for item: {item_name}")
            return None
        
        return {
            "item_name": item_name,
            "item_amount": item_amount,
            "item_rate": item_rate,
            "item_quantity": item_quantity
        }
    
    def _is_total_or_subtotal(self, item_name: str) -> bool:
        """Check if item name looks like a total or subtotal"""
        item_lower = item_name.lower().strip()
        
        total_keywords = [
            "total", "subtotal", "sub-total", "grand total",
            "final total", "net amount", "amount due",
            "balance", "sum", "total amount", "final amount"
        ]
        
        # Check if item name is primarily a total keyword
        for keyword in total_keywords:
            if keyword in item_lower and len(item_lower) < 30:
                # Additional check: if it's mostly just the keyword
                if item_lower.replace(keyword, "").strip() in ["", "-", ":", "="]:
                    return True
        
        return False
    
    def _normalize_page_type(self, page_type: str) -> str:
        """Normalize page type to allowed values"""
        page_type_lower = page_type.lower().strip()
        
        if "pharmacy" in page_type_lower:
            return "Pharmacy"
        elif "final" in page_type_lower:
            return "Final Bill"
        else:
            return "Bill Detail"
    
    def _deduplicate_items(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate items across pages using fuzzy matching
        
        Strategy:
        1. Track items by page
        2. For each page, check if items are duplicates of items in previous pages
        3. Use item name similarity and amount matching
        """
        seen_items = []  # Track items we've seen across pages
        deduplicated_pages = []
        
        for page in pages:
            deduplicated_page = {
                "page_no": page["page_no"],
                "page_type": page["page_type"],
                "bill_items": []
            }
            
            for item in page["bill_items"]:
                # Check if this item is a duplicate
                is_duplicate = False
                
                for seen_item in seen_items:
                    if self._are_items_duplicate(item, seen_item):
                        is_duplicate = True
                        logger.info(
                            f"Found duplicate item: '{item['item_name']}' "
                            f"(page {page['page_no']}) matches '{seen_item['item_name']}' "
                            f"(page {seen_item.get('page_no', 'unknown')})"
                        )
                        break
                
                if not is_duplicate:
                    # Add to current page and track it
                    item_with_page = item.copy()
                    item_with_page["page_no"] = page["page_no"]
                    seen_items.append(item_with_page)
                    deduplicated_page["bill_items"].append(item)
            
            deduplicated_pages.append(deduplicated_page)
        
        return deduplicated_pages
    
    def _are_items_duplicate(self, item1: Dict[str, Any], item2: Dict[str, Any]) -> bool:
        """Check if two items are duplicates"""
        name1 = item1["item_name"].lower().strip()
        name2 = item2["item_name"].lower().strip()
        
        # Exact name match
        if name1 == name2:
            return True
        
        # Similar name and similar amount (likely same item)
        name_similarity = self._calculate_name_similarity(name1, name2)
        amount_diff = abs(item1["item_amount"] - item2["item_amount"])
        
        # If names are very similar and amounts are close, likely duplicate
        if name_similarity > self.similarity_threshold:
            # Allow small differences in amount (rounding, etc.)
            if amount_diff < 0.01 or (amount_diff / max(abs(item1["item_amount"]), 0.01)) < 0.05:
                return True
        
        return False
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two item names"""
        # Simple similarity based on common words and characters
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0.0
        
        return intersection / union

