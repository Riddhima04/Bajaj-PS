"""
Document Processor - Handles downloading and processing documents (PDFs, images)
"""

import requests
import logging
import os
from typing import List, Dict, Optional
from io import BytesIO
from PIL import Image
import fitz  # PyMuPDF
import base64
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Processes documents from URLs and extracts page images"""
    
    def __init__(self):
        self.supported_formats = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
    
    async def process_document(self, document_url: str) -> List[Dict[str, any]]:
        """
        Download and process document, returning list of page data
        
        Args:
            document_url: URL of the document to process
            
        Returns:
            List of dictionaries with page number and image data
        """
        try:
            # Download document
            logger.info(f"Downloading document from: {document_url}")
            response = requests.get(document_url, timeout=30)
            response.raise_for_status()
            
            # Check if we got HTML instead of a file (common with Google Drive sharing links)
            content_type = response.headers.get('content-type', '').lower()
            content_preview = response.content[:500] if len(response.content) > 500 else response.content
            
            if 'text/html' in content_type or content_preview.startswith(b'<!DOCTYPE') or content_preview.startswith(b'<html') or b'<html' in content_preview.lower():
                error_msg = (
                    "The URL appears to be a sharing link (like Google Drive) that returns HTML instead of the file. "
                    "Please use a direct download link. For Google Drive: "
                    "https://drive.google.com/uc?export=download&id=FILE_ID. "
                    "Also ensure the file is set to 'Anyone with the link can view' in Google Drive settings."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Check if content is too small (likely an error page)
            if len(response.content) < 100:
                raise ValueError(
                    f"Downloaded content is too small ({len(response.content)} bytes). "
                    "This may indicate an error page or invalid file."
                )
            
            file_extension = self._get_file_extension(document_url)
            
            # Check file content (magic bytes) to determine file type
            # This is more reliable than content-type headers
            is_pdf = False
            is_image = False
            
            # Check for PDF (starts with %PDF)
            if response.content.startswith(b'%PDF'):
                is_pdf = True
                logger.info("Detected PDF from file content (magic bytes)")
            # Check for PNG
            elif response.content.startswith(b'\x89PNG\r\n\x1a\n'):
                is_image = True
                logger.info("Detected PNG from file content")
            # Check for JPEG
            elif response.content.startswith(b'\xff\xd8\xff'):
                is_image = True
                logger.info("Detected JPEG from file content")
            # Check for TIFF
            elif response.content.startswith(b'II*\x00') or response.content.startswith(b'MM\x00*'):
                is_image = True
                logger.info("Detected TIFF from file content")
            # Fallback to content-type and extension
            elif 'pdf' in content_type or file_extension == '.pdf':
                is_pdf = True
                logger.info("Detected PDF from content-type or extension")
            elif any(img_type in content_type for img_type in ['image', 'png', 'jpg', 'jpeg']):
                is_image = True
                logger.info("Detected image from content-type")
            
            pages_data = []
            
            if is_pdf:
                # Process PDF
                pages_data = await self._process_pdf(response.content)
            elif is_image:
                # Process image
                pages_data = await self._process_image(response.content, 1)
            else:
                # Try to process as image (fallback)
                logger.warning("File type not clearly identified, attempting to process as image")
                pages_data = await self._process_image(response.content, 1)
            
            logger.info(f"Processed {len(pages_data)} pages")
            return pages_data
            
        except requests.RequestException as e:
            logger.error(f"Error downloading document: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            raise
    
    async def _process_pdf(self, pdf_content: bytes) -> List[Dict[str, any]]:
        """Convert PDF pages to images using PyMuPDF"""
        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
            
            pages_data = []
            
            # Process each page
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Convert page to image (pixmap)
                # zoom factor of 2.0 gives approximately 300 DPI
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom = ~300 DPI
                pix = page.get_pixmap(matrix=mat)
                
                # Convert pixmap to PIL Image
                img_data = pix.tobytes("png")
                image = Image.open(BytesIO(img_data))
                
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Convert to base64
                img_buffer = BytesIO()
                image.save(img_buffer, format='PNG')
                img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
                
                pages_data.append({
                    "page_no": str(page_num + 1),
                    "image_base64": img_base64,
                    "image": image
                })
            
            pdf_document.close()
            
            logger.info(f"Converted {len(pages_data)} PDF pages to images")
            return pages_data
            
        except Exception as e:
            logger.error(f"Error converting PDF: {str(e)}")
            raise ValueError(f"Failed to process PDF: {str(e)}")
    
    async def _process_image(self, image_content: bytes, page_no: int = 1) -> List[Dict[str, any]]:
        """Process single image"""
        try:
            # Check if content is actually an image
            if len(image_content) < 100:
                raise ValueError("File too small - may not be a valid image")
            
            # Check for HTML content (common with Google Drive)
            if image_content[:100].startswith(b'<!DOCTYPE') or image_content[:100].startswith(b'<html') or b'<html' in image_content[:500].lower():
                raise ValueError(
                    "Received HTML content instead of image. "
                    "This usually means the URL is a sharing link. "
                    "For Google Drive, use: https://drive.google.com/uc?export=download&id=FILE_ID"
                )
            
            # Try to open image
            try:
                image = Image.open(BytesIO(image_content))
            except Exception as img_error:
                # Check file signature
                if image_content[:4] == b'%PDF':
                    raise ValueError(
                        "File appears to be a PDF. Please ensure PDFs are processed with .pdf extension in URL, "
                        "or the content-type header indicates PDF."
                    )
                raise ValueError(
                    f"Cannot identify image file format. Error: {str(img_error)}. "
                    f"Supported formats: PNG, JPG, JPEG, TIFF, BMP. "
                    f"File size: {len(image_content)} bytes. "
                    f"First bytes: {image_content[:20].hex()}"
                )
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to base64
            img_buffer = BytesIO()
            image.save(img_buffer, format='PNG')
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            return [{
                "page_no": str(page_no),
                "image_base64": img_base64,
                "image": image
            }]
            
        except ValueError:
            # Re-raise ValueError with better message
            raise
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise ValueError(f"Failed to process image: {str(e)}")
    
    def _get_file_extension(self, url: str) -> str:
        """Extract file extension from URL"""
        try:
            # Remove query parameters
            url_path = url.split('?')[0]
            # Get extension
            if '.' in url_path:
                return '.' + url_path.split('.')[-1].lower()
            return ''
        except:
            return ''

