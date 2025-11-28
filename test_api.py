"""
Test script for the Bill Extraction API
"""

import requests
import json
import sys

API_URL = "http://localhost:8000/extract-bill-data"


def test_extraction(document_url: str):
    """Test the bill extraction endpoint"""
    
    print(f"Testing extraction for document: {document_url}")
    print("-" * 60)
    
    try:
        response = requests.post(
            API_URL,
            json={"document": document_url},
            timeout=120  # Allow time for processing
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Extraction successful!")
            print("\nResponse:")
            print(json.dumps(result, indent=2))
            
            # Summary
            if result.get("is_success"):
                data = result.get("data", {})
                total_items = data.get("total_item_count", 0)
                pages = len(data.get("pagewise_line_items", []))
                
                print(f"\n📊 Summary:")
                print(f"   Pages processed: {pages}")
                print(f"   Total items: {total_items}")
                
                token_usage = result.get("token_usage", {})
                print(f"\n💰 Token Usage:")
                print(f"   Total tokens: {token_usage.get('total_tokens', 0)}")
                print(f"   Input tokens: {token_usage.get('input_tokens', 0)}")
                print(f"   Output tokens: {token_usage.get('output_tokens', 0)}")
                
                # Show items from each page
                print(f"\n📄 Page Details:")
                for page in data.get("pagewise_line_items", []):
                    print(f"\n   Page {page.get('page_no')} ({page.get('page_type')}):")
                    for item in page.get("bill_items", []):
                        print(f"      - {item.get('item_name')}: "
                              f"₹{item.get('item_amount')} "
                              f"(Qty: {item.get('item_quantity')}, "
                              f"Rate: {item.get('item_rate')})")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {str(e)}")
        print("\nMake sure the API server is running:")
        print("  python main.py")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_api.py <document_url>")
        print("\nExample:")
        print('  python test_api.py "https://example.com/bill.pdf"')
        sys.exit(1)
    
    document_url = sys.argv[1]
    test_extraction(document_url)

