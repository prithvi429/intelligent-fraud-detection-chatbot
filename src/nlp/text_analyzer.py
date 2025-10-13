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
import spacy
import threading
from spacy.matcher import Matcher
from sentence_transformers import SentenceTransformer, util
from textblob import TextBlob
from typing import List, Dict, Any, Optional

from src.config import config
from src.utils.logger import logger
from src.utils.cache import cache_get, cache_set
from src.fraud_engine.constants import SUSPICIOUS_PHRASES

# =========================================================
# ⚙️ Global Model Cache (thread-safe lazy load)
# =========================================================
_nlp = None
_model = None
_matcher = None
MODEL_LOAD_LOCK = threading.Lock()


# =========================================================
# 🧠 Model Loader
# =========================================================
def load_nlp_models():
    """Load spaCy and SentenceTransformer models safely (thread-safe lazy load)."""
    global _nlp, _model, _matcher
    with MODEL_LOAD_LOCK:
        try:
            if _nlp is None:
                _nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger"])
                logger.info("✅ spaCy model loaded.")

            if _model is None:
                _model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("✅ SentenceTransformer model loaded.")

            if _matcher is None:
                _matcher = Matcher(_nlp.vocab)
                _matcher.add(
                    "SUSPICIOUS_PATTERN",
                    [
                        [{"LOWER": {"IN": ["fake", "staged", "ghost", "exaggerated"]}}],
                        [{"LOWER": "quick"}, {"LOWER": "cash"}],
                        [{"ENT_TYPE": "DATE"}, {"LOWER": "injury"}],
                    ],
                )
                logger.debug("✅ spaCy matcher patterns initialized.")

        except Exception as e:
            logger.error(f"❌ NLP model loading error: {e}")


# =========================================================
# 🔍 Core Text Analysis
# =========================================================
def analyze_text(text: str, past_texts: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Analyze claim notes for fraud-related indicators.

    Args:
        text (str): Claim notes or description.
        past_texts (List[str], optional): Previous claims for similarity check.

    Returns:
        Dict[str, Any]: Extracted fraud-related NLP signals.
    """
    if not text or not text.strip():
        return {
            "suspicious_phrases": [],
            "entities": {},
            "keyword_count": 0,
            "similarity_scores": [],
            "sentiment": 0.0,
            "is_suspicious": False,
        }

    load_nlp_models()

    # Cache lookup
    cache_key = f"nlp:{hash(text)}"
    cached = cache_get(cache_key)
    if cached:
        logger.debug("🧠 Cache hit for text analysis.")
        return cached

    doc = _nlp(text.lower())

    # 1️⃣ Suspicious phrase detection
    suspicious_phrases = [kw for kw in SUSPICIOUS_PHRASES if kw in text.lower()]
    for _, start, end in _matcher(doc):
        phrase = doc[start:end].text
        if phrase not in suspicious_phrases:
            suspicious_phrases.append(phrase)
    keyword_count = len(suspicious_phrases)

    # 2️⃣ Entity extraction (NER)
    entities: Dict[str, List[str]] = {}
    for ent in doc.ents:
        entities.setdefault(ent.label_, []).append(ent.text)

    # Add monetary pattern manually
    money_matches = re.findall(r"\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?", text)
    if money_matches:
        entities.setdefault("MONEY", []).extend(money_matches)

    # 3️⃣ Semantic similarity (duplicate claims)
    similarity_scores = []
    max_similarity = 0.0
    if past_texts and _model:
        try:
            query_emb = _model.encode(text)
            for prev in past_texts:
                if not prev.strip():
                    continue
                prev_emb = _model.encode(prev)
                sim = util.cos_sim(query_emb, prev_emb)[0][0].item()
                similarity_scores.append(round(sim, 3))
            max_similarity = max(similarity_scores) if similarity_scores else 0.0
        except Exception as e:
            logger.warning(f"⚠️ Similarity check failed: {e}")

    # 4️⃣ Sentiment analysis
    sentiment = TextBlob(text).sentiment.polarity

    # 5️⃣ Suspicion scoring
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

    # Cache result (30 min)
    cache_set(cache_key, result, expire_seconds=1800)
    logger.debug(
        f"🧩 NLP Analysis: {keyword_count} keywords, sim={max_similarity:.2f}, sent={sentiment:.2f}"
    )
    return result


# =========================================================
# 🔗 Utility: Text Similarity
# =========================================================
def get_text_similarity(text1: str, text2: str) -> float:
    """Compute cosine similarity between two texts (0–1)."""
    load_nlp_models()
    if not _model:
        return 0.0
    try:
        emb1 = _model.encode(text1)
        emb2 = _model.encode(text2)
        return float(util.cos_sim(emb1, emb2)[0][0])
    except Exception as e:
        logger.warning(f"⚠️ Text similarity computation error: {e}")
        return 0.0


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    sample_text = "I had a staged accident to get quick cash. Injury on 2023-10-01. Amount $15000."
    previous_texts = ["Genuine accident in 2023-09-01 with Dr. Smith, $5000."]
    results = analyze_text(sample_text, previous_texts)
    print("Results:\n", results)
    print("\nSimilarity:", get_text_similarity(sample_text, previous_texts[0]))
