# Bill Extraction API

This project provides a FastAPI endpoint to extract line items, sub-totals and final totals from bill/invoice documents. It accepts a public document URL and returns structured, page-wise line items and totals.

Features
- Download and process PDF or image documents
- Convert PDF pages to images
- Send images to an LLM vision model to extract structured items
- Validate and deduplicate line items across pages

API
- POST `/extract-bill-data`
  - Request JSON: `{ "document": "<public_document_url>" }`
  - Response: JSON with `is_success`, `token_usage`, and `data.pagewise_line_items`.

Quick start (Windows / PowerShell)

1. Create and activate virtual environment (if not already):
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
```

2. Install requirements:
```powershell
pip install -r requirements.txt
```

3. Set environment variables (do NOT commit these):
```powershell
setx OPENAI_API_KEY "<your_api_key>"
setx USE_AZURE_OPENAI "false"
# If using Azure OpenAI, set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME
```

4. Run the API server:
```powershell
. .venv\Scripts\Activate.ps1
python .\main.py
```

5. Test the endpoint (PowerShell):
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/extract-bill-data" -Method Post -ContentType "application/json" -Body '{"document":"<document_url>"}'
```

Preparing to push to GitHub
1. Ensure `.env` or any file containing secrets is NOT committed. `.gitignore` already ignores `.env` and `.venv/`.
2. Initialize git and push:
```powershell
git init
git add .
git commit -m "Initial commit: bill extraction API"
git remote add origin <REMOTE_URL>
git branch -M main
git push -u origin main
```

Notes
- The project uses environment variables for API keys. Keep them secret and out of the repo.
- If you want me to add CI, tests, or a deployment manifest (Docker/GH Actions), tell me and I’ll add them.
# Bajaj Health Datathon - Bill Data Extraction Pipeline

## 📝 Overview

This repository contains the solution for the Bajaj Health Datathon. The goal of this project is to build an automated, accurate bill data extraction pipeline that processes medical invoices (images), extracts granular line-item details, and ensures mathematical reconciliation of totals without double-counting.

The solution is deployed as an API endpoint that accepts document URLs and returns structured JSON data containing page-wise items and calculated totals.

## 🚀 Problem Statement

The challenge requires designing a model to:

1. **Extract Data**: Identify and parse every line item (Name, Amount, Rate, Quantity) from multi-page medical bills.
2. **Avoid Redundancy**: Ensure line items are not double-counted (e.g., confusing sub-totals with line items).
3. **Reconcile Totals**: Calculate the `reconciled_amount` by summing individual line items to verify accuracy against the actual bill total.

## 🛠️ Tech Stack & Tools

- **Language**: Python 3.9+
- **Framework**: FastAPI (for API deployment)
- **AI/LLM Model**: Azure OpenAI GPT-4 Vision / OpenAI GPT-4 Vision
- **Image Processing**: Pillow (PIL), OpenCV
- **PDF Processing**: PyMuPDF (fitz)
- **Data Validation**: Pydantic
- **Containerization**: Docker (Optional)

## 🧠 Solution Approach

### 1. Pre-processing

The input image URL is fetched and processed. If the bill spans multiple pages, the system iterates through them to ensure no data is lost. PDFs are converted to high-resolution images (300 DPI) for optimal text recognition. Image enhancement techniques are applied if necessary to improve extraction accuracy.

### 2. Information Extraction

We utilize **Azure OpenAI GPT-4 Vision** (or OpenAI GPT-4 Vision) to interpret the layout of the invoice. The model is prompted to:

- Identify the main table structure.
- Distinguish between individual line items and summary rows (Sub-total, GST, Grand Total) to prevent double counting.
- Extract `item_name`, `item_rate`, `item_quantity`, and `item_amount`.

The model processes each page separately to ensure comprehensive extraction.

### 3. Post-processing & Reconciliation

A logical layer validates the extracted data:

- **Data Type Casting**: Ensures amounts and quantities are numerical.
- **Deduplication**: Uses fuzzy matching on item names and amount comparison to identify and remove duplicate items across pages.
- **Sub-total Detection**: Filters out rows containing keywords like "Total", "Sub Total", "Grand Total" from the line items.
- **Reconciliation Logic**: 
  $$\text{Reconciled Amount} = \sum (\text{Item Amount}_1 + \text{Item Amount}_2 + ... + \text{Item Amount}_n)$$
- **Validation**: The calculated sum is compared against the extracted document total to assign a confidence score (internal check).

## ⚙️ Installation & Setup

### Clone the Repository

```bash
git clone https://github.com/your-username/bajaj-health-datathon.git
cd bajaj-health-datathon
```

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Note on PDF Processing

PDF processing uses PyMuPDF (fitz), which is a pure Python library with no external dependencies. No additional system tools are required!

### Environment Variables

Create a `.env` file in the root directory and add your API keys:

**Option A: Azure OpenAI**
```env
USE_AZURE_OPENAI=true
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com
AZURE_OPENAI_API_KEY=your-azure-api-key-here
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

**Option B: Standard OpenAI**
```env
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4-vision-preview
```

### Run the Server

```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## 🔌 API Documentation

The solution exposes a single POST endpoint as required by the submission format.

### Endpoint: `/extract-bill-data`

**Method:** `POST`

### Request Body

The API accepts a JSON object containing the URL of the bill image.

```json
{
  "document": "https://hackrx.blob.core.windows.net/assets/datathon-IIT/sample_2.png?sv=2025-07-05..."
}
```

### Response Body

The API returns a structured JSON object including page-wise line items, the total count of items found, and the mathematically reconciled total amount.

```json
{
  "is_success": true,
  "token_usage": {
    "total_tokens": 5000,
    "input_tokens": 4000,
    "output_tokens": 1000
  },
  "data": {
    "pagewise_line_items": [
      {
        "page_no": "1",
        "page_type": "Bill Detail",
        "bill_items": [
          {
            "item_name": "Livi 300mg Tab",
            "item_amount": 448,
            "item_rate": 32,
            "item_quantity": 14
          },
          {
            "item_name": "Metnuro",
            "item_amount": 124.03,
            "item_rate": 17.72,
            "item_quantity": 7
          },
          {
            "item_name": "Pizat 4.5",
            "item_amount": 838.12,
            "item_rate": 419.06,
            "item_quantity": 2
          },
          {
            "item_name": "Supralite Os Syp",
            "item_amount": 289.69,
            "item_rate": 289.69,
            "item_quantity": 1
          }
        ]
      }
    ],
    "total_item_count": 4,
    "reconciled_amount": 1699.84
  }
}
```

## 📊 Evaluation Criteria Compliance

| Criteria | Implementation Status |
|----------|---------------------|
| **Accuracy of Line Items** | The model uses Azure OpenAI GPT-4 Vision to ensure high-fidelity text extraction with intelligent layout understanding. |
| **Reconciliation** | A dedicated post-processing script sums extracted `item_amount` values to generate `reconciled_amount`, ensuring mathematical consistency. |
| **No Double Counting** | Heuristics are applied to filter out "Total", "Subtotal", and "Balance Due" rows from the `bill_items` array. Additionally, fuzzy matching deduplicates items across pages. |
| **Output Format** | Strictly adheres to the JSON schema provided in the problem statement. |

## 📂 Project Structure

```
priya_ml_task/
├── main.py                    # Entry point for the API (FastAPI app)
├── services/
│   ├── __init__.py
│   ├── document_processor.py  # Core logic for document download and processing
│   ├── extraction_service.py  # Core logic for LLM interaction and parsing
│   └── data_validator.py       # Helper functions for validation and deduplication
├── requirements.txt           # Python dependencies
├── test_api.py                # Test script for API
├── .env                       # API Keys (not included in repo)
├── env.example.txt            # Environment variables template
├── Dockerfile                 # Docker deployment configuration
├── docker-compose.yml         # Docker Compose configuration
└── README.md                   # Project documentation
```

## 🧪 Testing

To test the API locally, you can use the test script:

```bash
python test_api.py "https://your-bill-url.com/bill.pdf"
```

Or use curl:

```bash
curl -X POST http://localhost:8000/extract-bill-data \
  -H "Content-Type: application/json" \
  -d '{"document": "https://link-to-sample-invoice.png"}'
```

Or visit the interactive API docs at: `http://localhost:8000/docs`

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up --build

# Or manually
docker build -t bill-extraction .
docker run -p 8000:8000 -e OPENAI_API_KEY=your-key bill-extraction
```

## 📚 Additional Documentation

- `QUICKSTART.md` - Quick setup guide
- `STEP_BY_STEP_GUIDE.md` - Detailed step-by-step instructions
- `TESTING_GUIDE.md` - Testing procedures
- `WHAT_TO_TEST.md` - What to test and validate
- `AZURE_SETUP.md` - Azure OpenAI configuration

## 👤 Author

Created for the Bajaj Health Datathon - Bill Extraction Task

## 📄 License

This project is created for the HackRx Datathon - IIT Bill Extraction Task
