"""
Invoice Processor
-----------------
Extracts structured data from unstructured invoices (PDF/image) using OCR.

- Local: pytesseract (Tesseract) for dev.
- Prod: AWS Textract for accuracy (handles tables/forms).

Output example:
{
  "amount": 15000.0,
  "date": "2023-10-01",
  "provider": "ABC Clinic",
  "items": [...],
  "full_text": "...",
  "confidence": "medium",
  "s3_url": "https://.../invoices/..."
}

Used for:
- Amount validation (high_amount alarm)
- Provider check (vendor_fraud)
- Date mismatch

Notes:
- For local PDFs, pdf2image requires Poppler installed on the host.
"""

import os
import re
import tempfile
from io import BytesIO
from datetime import datetime
from typing import Dict, Any, Optional, List

import boto3
from botocore.exceptions import ClientError
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

from src.config import config
from src.utils.logger import logger
from src.utils.cache import cache_get, cache_set
from src.utils.s3_handler import s3_handler  # singleton with upload_file/upload_bytes

# Configure Tesseract path if needed (Windows users often must set this)
# Example for Windows:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# Common Linux/Mac default works if tesseract is on PATH.


class InvoiceProcessor:
    def __init__(self):
        self.textract_client = None
        # Initialize Textract only if AWS creds are present
        if config.AWS_REGION and (os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_SECRET_ACCESS_KEY")):
            try:
                self.textract_client = boto3.client("textract", region_name=config.AWS_REGION)
                logger.info("✅ AWS Textract client initialized.")
            except Exception as e:
                logger.warning(f"Textract init failed: {e} – falling back to local OCR.")

    # ---------- Public API ----------

    def process_invoice(
        self,
        file_path: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        file_type: str = "pdf",          # "pdf" or "image"
        s3_prefix: str = "invoices",     # S3 folder/prefix
        s3_filename_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main method: Process an invoice via Textract (if available) or local OCR.
        - If `file_bytes` provided and Textract is available → use Textract.
        - Else if `file_path` provided → use local OCR (Tesseract).
        - Optionally uploads to S3 and returns `s3_url` in the result.
        """
        if not file_path and not file_bytes:
            return {"error": "No input file provided", "amount": 0.0, "date": None, "provider": None, "items": []}

        # Cache key by bytes hash or path mtime + size
        cache_key = None
        if file_bytes:
            cache_key = f"invoice:bytes:{hash(file_bytes)}"
        elif file_path and os.path.exists(file_path):
            stat = os.stat(file_path)
            cache_key = f"invoice:path:{file_path}:{stat.st_mtime_ns}:{stat.st_size}"

        cached = cache_get(cache_key) if cache_key else None
        if cached:
            logger.debug("🧠 Cache hit for invoice processing")
            return cached

        # Process
        if file_bytes and self.textract_client:
            result = self.process_invoice_textract(file_bytes, file_type=file_type)
        elif file_path:
            result = self.process_invoice_local(file_path)
        elif file_bytes:
            # No Textract; write to temp file and run local OCR
            with tempfile.NamedTemporaryFile(delete=True, suffix=f".{file_type}") as tmp:
                tmp.write(file_bytes)
                tmp.flush()
                result = self.process_invoice_local(tmp.name)
        else:
            result = {"error": "Unsupported input", "amount": 0.0, "date": None, "provider": None, "items": []}

        # Upload to S3 (best-effort)
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            fname = s3_filename_hint or (os.path.basename(file_path) if file_path else f"invoice_{timestamp}.{file_type}")
            s3_key = f"{s3_prefix}/{timestamp}_{fname}"

            if file_bytes:
                ct = "application/pdf" if file_type.lower() == "pdf" else "image/png"
                s3_url = s3_handler.upload_bytes(file_bytes, s3_key, content_type=ct)
            else:
                # file_path path upload
                ct = "application/pdf" if (file_path or "").lower().endswith(".pdf") else "image/png"
                s3_url = s3_handler.upload_file(file_path, s3_key, content_type=ct)

            if s3_url:
                result["s3_url"] = s3_url
        except Exception as e:
            logger.warning(f"S3 upload skipped/failed: {e}")

        # Cache result
        if cache_key:
            cache_set(cache_key, result, expire_seconds=3600)

        return result

    # ---------- OCR Implementations ----------

    def process_invoice_local(self, file_path: str) -> Dict[str, Any]:
        """
        Local OCR with Tesseract (for dev; supports PDF and images).
        """
        try:
            full_text = ""
            if file_path.lower().endswith(".pdf"):
                # NOTE: Requires Poppler installed for pdf2image to work
                images: List[Image.Image] = convert_from_path(file_path, dpi=300)
                for img in images:
                    full_text += pytesseract.image_to_string(img, lang="eng") + "\n"
            else:
                img = Image.open(file_path)
                full_text = pytesseract.image_to_string(img, lang="eng")

            extracted = self._extract_from_text(full_text)
            logger.debug(f"🧾 Local OCR extracted: amount={extracted.get('amount')} date={extracted.get('date')} provider={extracted.get('provider')}")
            return extracted

        except Exception as e:
            logger.error(f"Local OCR error for {file_path}: {e}")
            return {"error": str(e), "amount": 0.0, "date": None, "provider": None, "items": []}

    def process_invoice_textract(self, file_bytes: bytes, file_type: str = "pdf") -> Dict[str, Any]:
        """
        AWS Textract for production-grade OCR (tables/forms).
        """
        if not self.textract_client:
            logger.warning("Textract not available – use local OCR.")
            return {"error": "Textract unavailable", "amount": 0.0, "date": None, "provider": None, "items": []}

        try:
            if file_type.lower() == "image":
                # detect_document_text supports images (PNG/JPG)
                response = self.textract_client.detect_document_text(
                    Document={"Bytes": file_bytes}
                )
                lines = [b["Text"] for b in response.get("Blocks", []) if b.get("BlockType") == "LINE"]
                full_text = " ".join(lines)
            else:
                # analyze_document supports forms/tables (PDF or images)
                response = self.textract_client.analyze_document(
                    Document={"Bytes": file_bytes},
                    FeatureTypes=["TABLES", "FORMS"],
                )
                lines = [b["Text"] for b in response.get("Blocks", []) if b.get("BlockType") == "LINE"]
                full_text = " ".join(lines)

            extracted = self._extract_from_text(full_text)
            logger.debug(f"🧾 Textract extracted: amount={extracted.get('amount')} date={extracted.get('date')} provider={extracted.get('provider')}")
            return extracted

        except ClientError as e:
            logger.error(f"Textract API error: {e}")
            return {"error": str(e), "amount": 0.0, "date": None, "provider": None, "items": []}
        except Exception as e:
            logger.error(f"Unexpected Textract error: {e}")
            return {"error": str(e), "amount": 0.0, "date": None, "provider": None, "items": []}

    # ---------- Parsing Helpers ----------

    def _extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract key fields from OCR text using regex heuristics.
        - Amount: $1,234.56 or 1234.56
        - Date: MM/DD/YYYY or YYYY-MM-DD
        - Provider: "Provider: XYZ Clinic", "Bill from: ABC Hospital", "From: ..."
        - Items: lines containing numbers
        """
        # Amount (prefer the last, assuming it's "Total")
        amounts = re.findall(r'[\$]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', text)
        total_amount = 0.0
        if amounts:
            try:
                total_amount = float(amounts[-1].replace(",", ""))
            except Exception:
                total_amount = 0.0

        # Date
        dates = re.findall(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b', text)
        invoice_date = dates[0] if dates else None

        # Provider (basic heuristics)
        provider = None
        prov_patterns = [
            r'(?:provider|bill\s*from|from|to)[:\s]*([A-Z][A-Za-z&.\- ]{2,60})',
            r'(?:clinic|hospital|medical|services)[:\s]*([A-Z][A-Za-z&.\- ]{2,60})',
        ]
        for pat in prov_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                provider = m.group(1).strip()
                break

        # Items (simple heuristic: keep lines with numbers)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        items = [ln for ln in lines if re.search(r'\d', ln)]

        return {
            "amount": total_amount,
            "date": invoice_date,
            "provider": provider,
            "items": items[:10],          # cap to reduce payload
            "full_text": text[:1000],     # truncated for storage/logging
            "confidence": "medium",       # Textract can supply actual confidences if needed
        }
# =========================================================

# ---------- Manual Test ----------
if __name__ == "__main__":
    proc = InvoiceProcessor()

    # Example local image/PDF path test
    sample_path = os.getenv("SAMPLE_INVOICE_PATH", "")
    if sample_path and os.path.exists(sample_path):
        print("Local OCR result:", proc.process_invoice(file_path=sample_path, file_type="pdf" if sample_path.lower().endswith(".pdf") else "image"))

    # Example bytes test (simulate reading a PDF)
    # with open("invoice.pdf", "rb") as f:
    #     data = f.read()
    # print("Textract/bytes result:", proc.process_invoice(file_bytes=data, file_type="pdf", s3_filename_hint="invoice.pdf"))
