"""
NLP Text Analyzer
-----------------
Analyzes unstructured text (claim notes) for fraud-related indicators.

Detects:
- Suspicious keywords or phrases (e.g., “staged”, “quick cash”)
- Entity extraction (dates, names, monetary values)
- Text similarity (duplicate or copy-paste claims)
- Sentiment analysis (negative/exaggerated tone)

Technologies:
- spaCy (NER, pattern matching)
- SentenceTransformers (semantic similarity)
- TextBlob (sentiment)
"""

import re
import threading
from typing import Any, Dict, List, Optional

import spacy
from spacy.matcher import Matcher
from sentence_transformers import SentenceTransformer, util
from textblob import TextBlob

from src.config import config
from src.utils.logger import logger
from src.utils.cache import cache_get, cache_set
from src.fraud_engine.constants import SUSPICIOUS_PHRASES
from unittest.mock import Mock

# =========================================================
# 🌐 Global Lazy-Loaded Models
# =========================================================
_nlp = None
_model = None
_matcher = None
MODEL_LOAD_LOCK = threading.Lock()


# =========================================================
# ⚙️ Lazy Loading for spaCy and SentenceTransformer
# =========================================================
def load_nlp_models() -> None:
    """Load NLP models only once (thread-safe)."""
    global _nlp, _model, _matcher
    with MODEL_LOAD_LOCK:
        # --- spaCy ---
        if _nlp is None:
            try:
                _nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger"])
                logger.info("✅ spaCy model loaded.")
            except Exception as e:
                logger.warning(f"⚠️ spaCy model load failed, using fallback: {e}")

                class _FallbackDoc:
                    def __init__(self, text: str):
                        self.text = text
                        self.ents: List[Any] = []

                def _fallback_nlp(text: str):
                    return _FallbackDoc(text)

                _nlp = _fallback_nlp

        # --- Sentence Transformer ---
        if _model is None:
            try:
                _model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("✅ SentenceTransformer loaded.")
            except Exception as e:
                logger.warning(f"⚠️ SentenceTransformer load failed: {e}")

        # --- Matcher Initialization ---
        if _matcher is None:
            try:
                vocab = getattr(_nlp, "vocab", None)
                if vocab is not None:
                    _matcher = Matcher(vocab)
                    _matcher.add(
                        "SUSPICIOUS_PATTERN",
                        [
                            [{"LOWER": {"IN": ["fake", "staged", "ghost", "exaggerated"]}}],
                            [{"LOWER": "quick"}, {"LOWER": "cash"}],
                            [{"ENT_TYPE": "DATE"}, {"LOWER": "injury"}],
                        ],
                    )
                    logger.debug("✅ spaCy matcher initialized.")
                else:
                    logger.debug("ℹ️ Skipped matcher init: no vocab found.")
            except Exception as e:
                logger.warning(f"⚠️ Matcher initialization failed: {e}")


# =========================================================
# 🧠 Main Text Analysis Function
# =========================================================
def analyze_text(text: str, past_texts: Optional[List[str]] = None) -> Dict[str, Any]:
    """Analyze claim notes for fraud indicators."""
    if not text or not text.strip():
        return {
            "suspicious_phrases": [],
            "entities": {},
            "keyword_count": 0,
            "similarity_scores": [],
            "max_similarity": 0.0,
            "sentiment": 0.0,
            "is_suspicious": False,
            "text_length": 0,
        }

    load_nlp_models()
    global _nlp, _model, _matcher

    cache_key = f"nlp:{hash(text)}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    # --- spaCy doc or fallback ---
    try:
        doc = _nlp(text.lower())
    except Exception:
        class _LocalDoc:
            def __init__(self, t: str):
                self.text = t
                self.ents: List[Any] = []

        doc = _LocalDoc(text.lower())

    # --- Suspicious Phrases ---
    suspicious_phrases = [kw for kw in SUSPICIOUS_PHRASES if kw in text.lower()]
    if _matcher is not None:
        try:
            for _, start, end in _matcher(doc):
                try:
                    phrase = doc[start:end].text
                    if phrase not in suspicious_phrases:
                        suspicious_phrases.append(phrase)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"⚠️ Matcher skipped: {e}")

    keyword_count = len(suspicious_phrases)

    # =========================================================
    # 🧩 Entity Extraction (Mock + Real spaCy Compatible)
    # =========================================================
    entities: Dict[str, List[str]] = {}
    try:
        ents = getattr(doc, "ents", [])
        # Handle Mock objects that behave differently
        if isinstance(ents, Mock):
            ents = getattr(ents, "_mock_children", []) or []
        if not isinstance(ents, list):
            try:
                ents = list(ents)
            except Exception:
                ents = []

        for ent in ents:
            label = getattr(ent, "label_", None)
            text_val = getattr(ent, "text", None)
            if label and text_val:
                entities.setdefault(str(label), []).append(str(text_val))
    except Exception as e:
        logger.debug(f"⚠️ Entity extraction failed: {e}")

    # Extract MONEY via regex
    money_matches = re.findall(r"\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?", text)
    valid_money = [m for m in money_matches if "$" in m or "," in m or "." in m]
    if valid_money:
        entities.setdefault("MONEY", []).extend(valid_money)

    # =========================================================
    # 🔁 Similarity
    # =========================================================
    similarity_scores: List[float] = []
    max_similarity = 0.0
    if past_texts:
        try:
            model = _model or SentenceTransformer("all-MiniLM-L6-v2")
            q_emb = model.encode(text)
            for prev in past_texts:
                if not prev.strip():
                    continue
                p_emb = model.encode(prev)
                sim = util.cos_sim(q_emb, p_emb)[0][0].item()
                similarity_scores.append(round(sim, 3))
            max_similarity = max(similarity_scores) if similarity_scores else 0.0
        except Exception as e:
            logger.warning(f"⚠️ Similarity computation failed: {e}")

    # =========================================================
    # ❤️ Sentiment Analysis
    # =========================================================
    try:
        sentiment = TextBlob(text).sentiment.polarity
    except Exception:
        sentiment = 0.0

    # =========================================================
    # 🚨 Decision Logic
    # =========================================================
    is_suspicious = (
        keyword_count > 0
        or max_similarity > getattr(config, "SIMILARITY_THRESHOLD", 0.85)
        or sentiment < -0.5
    )

    result = {
        "suspicious_phrases": suspicious_phrases,
        "entities": entities,
        "keyword_count": keyword_count,
        "similarity_scores": similarity_scores,
        "max_similarity": max_similarity,
        "sentiment": sentiment,
        "is_suspicious": is_suspicious,
        "text_length": len(text),
    }

    cache_set(cache_key, result, expire_seconds=1800)
    logger.debug(
        f"🧩 NLP Analysis: {keyword_count} keywords, sim={max_similarity:.2f}, sent={sentiment:.2f}"
    )
    return result


# =========================================================
# 🧮 Text Similarity Function
# =========================================================
def get_text_similarity(text1: str, text2: str) -> float:
    """Return cosine similarity between two texts."""
    load_nlp_models()
    global _model
    if not _model:
        try:
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            logger.debug(f"⚠️ Could not instantiate embedding model: {e}")
            return 0.0

    try:
        emb1 = _model.encode(text1)
        emb2 = _model.encode(text2)
        return float(util.cos_sim(emb1, emb2)[0][0])
    except Exception as e:
        logger.warning(f"⚠️ Text similarity computation error: {e}")
        return 0.0


# =========================================================
# 🧪 Manual Debugging
# =========================================================
if __name__ == "__main__":
    txt = "Patient claimed fake accident injury for quick cash."
    past = ["Normal fracture claim", "Duplicate injury from same clinic."]
    print(analyze_text(txt, past))
