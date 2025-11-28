"""
Bill Extractor - Uses LLM to extract structured data from bill images
"""

import os
import logging
import asyncio
from typing import List, Dict, Optional, Any
import json
from openai import OpenAI, AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class BillExtractor:
    """Service for extracting bill data using LLM vision models"""
    
    def __init__(self):
        use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
        
        if use_azure:
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            
            if not azure_endpoint or not azure_api_key:
                raise ValueError("Azure OpenAI requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY")
            if not deployment_name:
                raise ValueError("Azure OpenAI requires AZURE_OPENAI_DEPLOYMENT_NAME")
            azure_endpoint = azure_endpoint.rstrip('/')
            from openai import AzureOpenAI
            self.client = AzureOpenAI(api_key=azure_api_key, api_version=azure_api_version, azure_endpoint=azure_endpoint)
            self.model = deployment_name
            logger.info(f"Using Azure OpenAI Deployment: {deployment_name}")
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            self.client = OpenAI(api_key=api_key)
            self.model = os.getenv("OPENAI_MODEL", "gpt-4-vision-preview")
            logger.info(f"Using standard OpenAI with model: {self.model}")
        
        self.token_usage = {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0}

    async def extract_bill_data(self, pages_data: List[Dict[str, any]]) -> Dict[str, Any]:
        self.token_usage = {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0}
        pagewise_line_items = []
        for idx, page_data in enumerate(pages_data):
            page_no = page_data["page_no"]
            image_base64 = page_data["image_base64"]
            logger.info(f"Extracting data from page {page_no}")
            if idx > 0:
                delay = float(os.getenv("PAGE_PROCESSING_DELAY", "2.0"))
                await asyncio.sleep(delay)
            page_result = await self._extract_page_data(page_no, image_base64)
            if page_result:
                pagewise_line_items.append(page_result)
        return {"pagewise_line_items": pagewise_line_items, "token_usage": self.token_usage}

    async def _extract_page_data(self, page_no: str, image_base64: str) -> Optional[Dict[str, Any]]:
        system_prompt = """You are an expert at extracting structured data from bills and invoices. """
        user_prompt = f"Extract all line items from this page (page {page_no}) of the bill."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                    ]}
                ],
                max_tokens=4000,
                temperature=0.1
            )
            usage = response.usage
            self.token_usage["total_tokens"] += usage.total_tokens
            self.token_usage["input_tokens"] += usage.prompt_tokens
            self.token_usage["output_tokens"] += usage.completion_tokens
            content = response.choices[0].message.content
            json_str = self._extract_json_from_response(content)
            page_data = json.loads(json_str)
            if "bill_items" not in page_data:
                page_data["bill_items"] = []
            for item in page_data["bill_items"]:
                item.setdefault("item_name", "")
                item.setdefault("item_amount", 0.0)
                item.setdefault("item_rate", 0.0)
                item.setdefault("item_quantity", 0.0)
                try:
                    item["item_amount"] = float(item["item_amount"])
                    item["item_rate"] = float(item["item_rate"])
                    item["item_quantity"] = float(item["item_quantity"])
                except (ValueError, TypeError):
                    item["item_amount"] = 0.0
                    item["item_rate"] = 0.0
                    item["item_quantity"] = 0.0
            return page_data
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for page {page_no}: {str(e)}")
            content_preview = content[:500] if 'content' in locals() else "No content"
            logger.error(f"Response content: {content_preview}")
            return {"page_no": page_no, "page_type": "Bill Detail", "bill_items": []}
        except Exception as e:
            logger.error(f"Error extracting data from page {page_no}: {str(e)}")
            return {"page_no": page_no, "page_type": "Bill Detail", "bill_items": []}

    def _extract_json_from_response(self, content: str) -> str:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx >= 0 and end_idx > start_idx:
            return content[start_idx:end_idx]
        return content
