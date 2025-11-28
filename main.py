"""
Bill Extraction API - Main FastAPI Application
Extracts line items, sub-totals, and final totals from multi-page bills/invoices
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.doc_reader import DocReader
from services.extractor import BillExtractor
from services.validator import ValidationEngine

# --- Configuration & Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
api_logger = logging.getLogger(__name__)

# --- Data Models (Moved to top for clarity) ---

class UsageMetrics(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int

class LineEntry(BaseModel):
    # Field names kept identical to ensure mapping with service output remains valid
    item_name: str
    item_amount: float
    item_rate: float
    item_quantity: float

class PageContent(BaseModel):
    page_no: str
    page_type: str  # "Bill Detail" | "Final Bill" | "Pharmacy"
    bill_items: List[LineEntry]

class ProcessedResult(BaseModel):
    pagewise_line_items: List[PageContent]
    total_item_count: int
    reconciled_amount: float

class ServiceOutput(BaseModel):
    is_success: bool
    token_usage: UsageMetrics
    data: ProcessedResult

class InvoiceUrlInput(BaseModel):
    document: str = Field(..., description="URL of the document to process")

# --- Application Initialization ---

app = FastAPI(
    title="Bill Extraction API",
    description="Extract line items, sub-totals, and totals from bills/invoices",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Service Instantiation ---
# Renamed instances
reader_service = DocReader()
parsing_service = BillExtractor()
audit_service = ValidationEngine()

# --- Route Handlers ---

@app.get("/health")
async def check_api_status():
    # Moved health check before root
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/")
async def read_index():
    return {
        "message": "Bill Extraction API",
        "version": "1.0.0",
        "endpoint": "/extract-bill-data"
    }

@app.post("/extract-bill-data", response_model=ServiceOutput)
async def process_invoice_request(payload: InvoiceUrlInput):
    """
    Extract line items, sub-totals, and final totals from a bill/invoice document.
    
    Args:
        payload: Contains document URL
        
    Returns:
        Structured response with pagewise line items and totals
    """
    try:
        api_logger.info(f"Processing document: {payload.document}")
        
        # Step 1: Download and process document
        raw_page_content = await reader_service.process_document(payload.document)
        if not raw_page_content:
            raise HTTPException(
                status_code=400,
                detail="Failed to process document. Please check the document URL."
            )
        
        api_logger.info(f"Document processed: {len(raw_page_content)} pages found")
        
        # Step 2: Extract data using LLM
        llm_output = await parsing_service.extract_bill_data(raw_page_content)
        
        if not llm_output or not llm_output.get("pagewise_line_items"):
            raise HTTPException(
                status_code=500,
                detail="Failed to extract data from document"
            )
        
        # Step 3: Validate and deduplicate data
        clean_data = audit_service.validate_and_deduplicate(
            llm_output["pagewise_line_items"]
        )
        
        # Step 4: Calculate total item count
        item_count_total = sum(
            len(page_group["bill_items"]) for page_group in clean_data
        )
        
        # Step 5: Calculate reconciled amount (sum of all item amounts)
        calculated_total_sum = 0.0
        for page_group in clean_data:
            for entry in page_group["bill_items"]:
                calculated_total_sum += entry.get("item_amount", 0.0)
        
        # Round to 2 decimal places for currency
        calculated_total_sum = round(calculated_total_sum, 2)
        
        # Step 6: Prepare response
        final_result = ProcessedResult(
            pagewise_line_items=[
                PageContent(**p) for p in clean_data
            ],
            total_item_count=item_count_total,
            reconciled_amount=calculated_total_sum
        )
        
        usage_stats = llm_output.get("token_usage", {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0
        })
        
        return ServiceOutput(
            is_success=True,
            token_usage=UsageMetrics(**usage_stats),
            data=final_result
        )
        
    except HTTPException:
        raise
    except Exception as err:
        api_logger.error(f"Error processing document: {str(err)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(err)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)