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
from unittest.mock import Mock

import spacy
from spacy.matcher import Matcher
from sentence_transformers import SentenceTransformer, util
from textblob import TextBlob

from src.config import config
from src.utils.logger import logger
from src.utils.cache import cache_get, cache_set
from src.fraud_engine.constants import SUSPICIOUS_PHRASES

# =========================================================
# 🌐 Global Lazy-Loaded Models
# =========================================================
_nlp = None
_model = None
_matcher = None
_MODEL_LOCK = threading.Lock()


# =========================================================
# ⚙️ Load NLP Models Lazily (thread-safe)
# =========================================================
def load_nlp_models() -> None:
    """Load spaCy and SentenceTransformer models only once (lazy-load)."""
    global _nlp, _model, _matcher
    with _MODEL_LOCK:
        # --- spaCy ---
        if _nlp is None:
            try:
                _nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger"])
                logger.info("✅ spaCy model loaded.")
            except Exception as e:
                logger.warning(f"⚠️ spaCy load failed; using fallback: {e}")

                class _FallbackDoc:
                    def __init__(self, text: str):
                        self.text = text
                        self.ents: List[Any] = []

                def _fallback_nlp(txt: str):
                    return _FallbackDoc(txt)

                _nlp = _fallback_nlp

        # --- SentenceTransformer ---
        if _model is None:
            try:
                _model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("✅ SentenceTransformer loaded.")
            except Exception as e:
                logger.warning(f"⚠️ SentenceTransformer load failed: {e}")

        # --- Matcher ---
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
                    logger.debug("ℹ️ No vocab found; skipping matcher initialization.")
            except Exception as e:
                logger.warning(f"⚠️ Matcher initialization failed: {e}")


# =========================================================
# 🧠 Analyze Text for Fraud Indicators
# =========================================================
def analyze_text(text: str, past_texts: Optional[List[str]] = None) -> Dict[str, Any]:
    """Analyze claim notes for suspicious content, entities, similarity, and sentiment."""
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

    # --- Cache ---
    cache_key = f"nlp:{hash(text)}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    # --- spaCy doc (fallback-safe) ---
    try:
        doc = _nlp(text.lower())
    except Exception:
        class _LocalDoc:
            def __init__(self, t: str):
                self.text = t
                self.ents: List[Any] = []

        doc = _LocalDoc(text.lower())

    # --- Suspicious keyword detection ---
    suspicious_phrases = [kw for kw in SUSPICIOUS_PHRASES if kw in text.lower()]
    if _matcher:
        try:
            for _, start, end in _matcher(doc):
                try:
                    phrase = doc[start:end].text
                    if phrase not in suspicious_phrases:
                        suspicious_phrases.append(phrase)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"⚠️ Matcher execution skipped: {e}")

    keyword_count = len(suspicious_phrases)

    # =========================================================
    # 🧩 Entity Extraction (Mock + spaCy Compatible)
    # =========================================================
    entities: Dict[str, List[str]] = {}
    try:
        ents = getattr(doc, "ents", [])

        # Convert Mock to iterable
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

    # --- MONEY extraction ---
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
            logger.debug(f"⚠️ Similarity computation failed: {e}")

    # =========================================================
    # ❤️ Sentiment Analysis
    # =========================================================
    try:
        sentiment = TextBlob(text).sentiment.polarity
    except Exception as e:
        logger.debug(f"⚠️ Sentiment analysis failed: {e}")
        sentiment = 0.0

    # =========================================================
    # 🚨 Suspicion Classification
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
# 🧮 Text Similarity Utility
# =========================================================
def get_text_similarity(text1: str, text2: str) -> float:
    """Return cosine similarity between two texts."""
    load_nlp_models()
    global _model
    try:
        model = _model or SentenceTransformer("all-MiniLM-L6-v2")
        emb1 = model.encode(text1)
        emb2 = model.encode(text2)
        return float(util.cos_sim(emb1, emb2)[0][0])
    except Exception as e:
        logger.debug(f"⚠️ Text similarity computation error: {e}")
        return 0.0


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    txt = "Patient claimed fake accident injury for quick cash."
    past = ["Normal fracture claim", "Duplicate injury from same clinic."]
    print(analyze_text(txt, past))
