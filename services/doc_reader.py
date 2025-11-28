"""
Doc Reader - Handles downloading and processing documents (PDFs, images)
"""

import requests
import logging
from typing import List, Dict, Optional
from io import BytesIO
from PIL import Image
import fitz  # PyMuPDF
import base64
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DocReader:
    """Processes documents from URLs and extracts page images"""
    
    def __init__(self):
        self.supported_formats = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
    
    async def process_document(self, document_url: str) -> List[Dict[str, any]]:
        """
        Download and process document, returning list of page data
        """
        try:
            logger.info(f"Downloading document from: {document_url}")
            response = requests.get(document_url, timeout=30)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            content_preview = response.content[:500] if len(response.content) > 500 else response.content

            if 'text/html' in content_type or content_preview.startswith(b'<!DOCTYPE') or content_preview.startswith(b'<html') or b'<html' in content_preview.lower():
                error_msg = (
                    "The URL appears to be a sharing link that returns HTML instead of the file. "
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            if len(response.content) < 100:
                raise ValueError(f"Downloaded content is too small ({len(response.content)} bytes).")

            file_extension = self._get_file_extension(document_url)

            is_pdf = False
            is_image = False

            if response.content.startswith(b'%PDF'):
                is_pdf = True
                logger.info("Detected PDF from file content (magic bytes)")
            elif response.content.startswith(b'\x89PNG\r\n\x1a\n'):
                is_image = True
                logger.info("Detected PNG from file content")
            elif response.content.startswith(b'\xff\xd8\xff'):
                is_image = True
                logger.info("Detected JPEG from file content")
            elif response.content.startswith(b'II*\x00') or response.content.startswith(b'MM\x00*'):
                is_image = True
                logger.info("Detected TIFF from file content")
            elif 'pdf' in content_type or file_extension == '.pdf':
                is_pdf = True
                logger.info("Detected PDF from content-type or extension")
            elif any(img_type in content_type for img_type in ['image', 'png', 'jpg', 'jpeg']):
                is_image = True
                logger.info("Detected image from content-type")

            pages_data = []

            if is_pdf:
                pages_data = await self._process_pdf(response.content)
            elif is_image:
                pages_data = await self._process_image(response.content, 1)
            else:
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
        try:
            pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
            pages_data = []
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                image = Image.open(BytesIO(img_data))
                if image.mode != 'RGB':
                    image = image.convert('RGB')
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
        try:
            if len(image_content) < 100:
                raise ValueError("File too small - may not be a valid image")
            if image_content[:100].startswith(b'<!DOCTYPE') or image_content[:100].startswith(b'<html') or b'<html' in image_content[:500].lower():
                raise ValueError("Received HTML content instead of image.")
            try:
                image = Image.open(BytesIO(image_content))
            except Exception as img_error:
                if image_content[:4] == b'%PDF':
                    raise ValueError("File appears to be a PDF.")
                raise ValueError(f"Cannot identify image file format. Error: {str(img_error)}")
            if image.mode != 'RGB':
                image = image.convert('RGB')
            img_buffer = BytesIO()
            image.save(img_buffer, format='PNG')
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            return [{
                "page_no": str(page_no),
                "image_base64": img_base64,
                "image": image
            }]
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise ValueError(f"Failed to process image: {str(e)}")

    def _get_file_extension(self, url: str) -> str:
        try:
            url_path = url.split('?')[0]
            if '.' in url_path:
                return '.' + url_path.split('.')[-1].lower()
            return ''
        except:
            return ''
