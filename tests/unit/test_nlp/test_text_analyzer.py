# tests/unit/test_nlp.py
"""
Unit Tests: NLP Components
--------------------------
Tests:
- src/nlp/text_analyzer.py (analyze_text, get_text_similarity, lazy loading & caching)
- src/nlp/invoice_processor.py (InvoiceProcessor.process_invoice_* and _extract_from_text)
"""

import pytest
from unittest.mock import Mock, patch
import numpy as np

from src.nlp.text_analyzer import analyze_text, get_text_similarity, load_nlp_models
from src.nlp.invoice_processor import InvoiceProcessor


# ----------------------
# Sample Text Fixtures
# ----------------------
NORMAL_TEXT = "Normal claim: minor injury on 2023-10-01 at local clinic."
SUSPICIOUS_TEXT = "Staged accident for quick cash, exaggerated pain with fake doctor."
PAST_TEXTS = ["Previous normal claim: real injury at trusted hospital."]

SAMPLE_OCR_TEXT = """
Invoice from ABC Clinic
Date: 10/01/2023
Total Amount: $1,500.00
Items: Consultation $200, X-ray $300, Medication $1,000
"""


# ===========================
# text_analyzer.py — analyze
# ===========================
@patch("src.nlp.text_analyzer.TextBlob")
@patch("src.nlp.text_analyzer.util")
@patch("src.nlp.text_analyzer.SentenceTransformer")
@patch("src.nlp.text_analyzer.spacy")
def test_analyze_text_normal(mock_spacy, mock_st, mock_util, mock_blob):
    """Normal text → no suspicious phrases, low similarity, neutral sentiment."""
    # spaCy mock
    mock_nlp = Mock()
    mock_doc = Mock()
    mock_doc.ents = []         # no entities
    mock_doc.text = NORMAL_TEXT.lower()
    mock_nlp.return_value = mock_doc
    mock_spacy.load.return_value = mock_nlp

    # Matcher returns no matches (we don’t need to set it explicitly; analyze_text uses _matcher)
    # Embeddings similarity low
    mock_model = Mock()
    mock_model.encode.return_value = np.array([0.1, 0.1])
    mock_st.return_value = mock_model
    mock_util.cos_sim.return_value = np.array([[0.2]])

    # Sentiment neutral
    mock_blob.return_value.sentiment.polarity = 0.1

    result = analyze_text(NORMAL_TEXT, PAST_TEXTS)
    assert result["suspicious_phrases"] == []
    assert result["keyword_count"] == 0
    assert result["entities"] == {}
    assert result["similarity_scores"] == [0.2]
    assert result["max_similarity"] == 0.2
    assert result["sentiment"] == 0.1
    assert result["is_suspicious"] is False
    assert result["text_length"] == len(NORMAL_TEXT)


@patch("src.nlp.text_analyzer.TextBlob")
@patch("src.nlp.text_analyzer.util")
@patch("src.nlp.text_analyzer.SentenceTransformer")
@patch("src.nlp.text_analyzer.spacy")
def test_analyze_text_suspicious(mock_spacy, mock_st, mock_util, mock_blob):
    """Suspicious text → phrases found, entities, high similarity, negative sentiment."""
    # spaCy mock with ents
    mock_nlp = Mock()
    mock_doc = Mock()
    ent_date = Mock(label_="DATE", text="2023-10-01")
    ent_person = Mock(label_="PERSON", text="fake doctor")
    mock_doc.ents = [ent_date, ent_person]
    mock_doc.text = SUSPICIOUS_TEXT.lower()
    mock_nlp.return_value = mock_doc
    mock_spacy.load.return_value = mock_nlp

    # We don’t directly call matcher in tests (patterns live in module), but suspicious phrases include
    # words from SUSPICIOUS_PHRASES ('staged', 'quick cash', etc.) in the input.
    # Embeddings similarity high
    mock_model = Mock()
    mock_model.encode.return_value = np.array([0.9, 0.9])
    mock_st.return_value = mock_model
    mock_util.cos_sim.return_value = np.array([[0.85]])

    # Negative sentiment
    mock_blob.return_value.sentiment.polarity = -0.4

    # Lower similarity threshold to 0.8 (already default ~0.8, but make explicit)
    with patch("src.nlp.text_analyzer.config.SIMILARITY_THRESHOLD", 0.8):
        result = analyze_text(SUSPICIOUS_TEXT, PAST_TEXTS)

    # Suspicious phrases should include terms present in SUSPICIOUS_TEXT
    assert any(p in result["suspicious_phrases"] for p in ["staged", "quick cash"])
    assert result["keyword_count"] >= 1
    # Entities captured with labels
    assert result["entities"].get("DATE") == ["2023-10-01"]
    assert result["entities"].get("PERSON") == ["fake doctor"]
    assert result["similarity_scores"] == [0.85]
    assert result["max_similarity"] == 0.85
    assert result["sentiment"] == -0.4
    assert result["is_suspicious"] is True


@patch("src.nlp.text_analyzer.spacy")
def test_analyze_text_empty(mock_spacy):
    """Empty text → empty results & not suspicious."""
    mock_nlp = Mock()
    mock_doc = Mock(ents=[], text="")
    mock_nlp.return_value = mock_doc
    mock_spacy.load.return_value = mock_nlp

    result = analyze_text("")
    assert result["suspicious_phrases"] == []
    assert result["keyword_count"] == 0
    assert result["entities"] == {}
    assert result["similarity_scores"] == []
    assert result["max_similarity"] == 0.0
    assert result["sentiment"] == 0.0
    assert result["is_suspicious"] is False
    assert result["text_length"] == 0


@patch("src.nlp.text_analyzer.util")
@patch("src.nlp.text_analyzer.SentenceTransformer")
def test_get_text_similarity(mock_st, mock_util):
    """Cosine similarity path returns 0–1 float."""
    model = Mock()
    model.encode.side_effect = [np.array([1, 0]), np.array([0.8, 0.6])]
    mock_st.return_value = model
    mock_util.cos_sim.return_value = np.array([[0.92]])

    sim = get_text_similarity("Text1", "Similar text2")
    assert sim == 0.92
    assert 0.0 <= sim <= 1.0


@patch("src.nlp.text_analyzer.SentenceTransformer", side_effect=Exception("load error"))
def test_get_text_similarity_no_model(_mock_st):
    """If embedding model fails to load, similarity returns 0.0 gracefully."""
    sim = get_text_similarity("A", "B")
    assert sim == 0.0


def test_load_nlp_models_called_once():
    """Lazy load only once."""
    with patch("src.nlp.text_analyzer.spacy.load") as m1, patch(
        "src.nlp.text_analyzer.SentenceTransformer"
    ) as m2:
        # First call triggers load
        analyze_text(NORMAL_TEXT)
        # Second call reuses
        analyze_text(SUSPICIOUS_TEXT)
        assert m1.call_count == 1
        assert m2.call_count == 1


# ====================================
# invoice_processor.py — OCR & Textract
# ====================================
def test_extract_from_text_normal():
    """_extract_from_text parses amount/date/provider/items correctly."""
    proc = InvoiceProcessor()
    extracted = proc._extract_from_text(SAMPLE_OCR_TEXT)

    assert extracted["amount"] == 1500.0
    assert extracted["date"] == "10/01/2023"
    assert extracted["provider"] == "ABC Clinic"
    assert len(extracted["items"]) >= 3
    assert "Consultation" in extracted["items"][0]
    assert len(extracted["full_text"]) <= 500


def test_extract_from_text_no_amount():
    """No total amount → amount=0.0 but date still extracted."""
    proc = InvoiceProcessor()
    txt = SAMPLE_OCR_TEXT.replace("$1,500.00", "")
    extracted = proc._extract_from_text(txt)
    assert extracted["amount"] == 0.0
    assert extracted["date"] == "10/01/2023"


def test_extract_from_text_multiple_amounts():
    """Multiple amounts → last one used as total (per implementation)."""
    proc = InvoiceProcessor()
    multi = SAMPLE_OCR_TEXT + "\nSubtotal: $1,200.00 Total: $1,500.00"
    extracted = proc._extract_from_text(multi)
    assert extracted["amount"] == 1500.0


@patch("src.nlp.invoice_processor.convert_from_path")
@patch("src.nlp.invoice_processor.pytesseract")
def test_process_invoice_local_pdf(mock_tess, mock_convert):
    """PDF → images → OCR → extract."""
    # One image page
    img = Mock()
    mock_convert.return_value = [img]
    mock_tess.image_to_string.return_value = SAMPLE_OCR_TEXT

    proc = InvoiceProcessor()
    res = proc.process_invoice_local("invoice.pdf")

    mock_convert.assert_called_once_with("invoice.pdf", dpi=300)
    mock_tess.image_to_string.assert_called_with(img, lang="eng")
    assert res["amount"] == 1500.0


@patch("src.nlp.invoice_processor.pytesseract")
def test_process_invoice_local_image(mock_tess):
    """Image path → direct OCR."""
    img = Mock()
    mock_tess.image_to_string.return_value = SAMPLE_OCR_TEXT
    proc = InvoiceProcessor()
    with patch("PIL.Image.open", return_value=img):
        res = proc.process_invoice_local("scan.jpg")

    mock_tess.image_to_string.assert_called_with(img, lang="eng")
    assert res["amount"] == 1500.0


@patch("src.nlp.invoice_processor.pytesseract")
def test_process_invoice_local_error(mock_tess):
    """OCR error → error dict with safe defaults."""
    mock_tess.image_to_string.side_effect = Exception("OCR failed")
    proc = InvoiceProcessor()
    res = proc.process_invoice_local("bad.jpg")
    assert "error" in res
    assert res["amount"] == 0.0
    assert res["date"] is None


@patch("boto3.client")
def test_process_invoice_textract_normal(mock_boto):
    """Textract happy path (image bytes)."""
    client = Mock()
    mock_boto.return_value = client
    client.detect_document_text.return_value = {
        "Blocks": [
            {"BlockType": "LINE", "Text": "Invoice from ABC Clinic"},
            {"BlockType": "LINE", "Text": "Date: 10/01/2023"},
            {"BlockType": "LINE", "Text": "Total Amount: $1,500.00"},
        ]
    }

    proc = InvoiceProcessor()
    # Force textract client
    proc.textract_client = client
    res = proc.process_invoice_textract(b"imgbytes", "image")

    client.detect_document_text.assert_called_once()
    assert res["amount"] == 1500.0
    assert "ABC Clinic" in res["provider"]


@patch("boto3.client")
def test_process_invoice_textract_error(mock_boto):
    """Textract failure → error dict."""
    client = Mock()
    mock_boto.return_value = client
    client.detect_document_text.side_effect = Exception("Textract failed")

    proc = InvoiceProcessor()
    proc.textract_client = client
    res = proc.process_invoice_textract(b"bad", "image")

    assert "error" in res
    assert res["amount"] == 0.0


def test_process_invoice_main_local_fallback():
    """process_invoice chooses local path for bytes when Textract is absent; file_path uses local."""
    proc = InvoiceProcessor()
    # No Textract client set; bytes route will fallback to local via temp file path
    with patch.object(proc, "process_invoice_textract", return_value={"error": "Textract unavailable"}), \
         patch.object(proc, "process_invoice_local", return_value={"amount": 2000.0}):
        res_bytes = proc.process_invoice(file_bytes=b"123", file_type="pdf")
    assert res_bytes["amount"] == 2000.0

    with patch.object(proc, "process_invoice_local", return_value={"amount": 3000.0}):
        res_file = proc.process_invoice(file_path="doc.pdf")
    assert res_file["amount"] == 3000.0
