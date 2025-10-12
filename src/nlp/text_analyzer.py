def extract_keywords(text: str):
    return []
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
- spaCy (NER, matcher)
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
from src.fraud_engine.alarms import SUSPICIOUS_PHRASES

# =========================================================
# ⚙️ Global Model Cache
# =========================================================
_nlp = None
_model = None
_matcher = None
MODEL_LOAD_LOCK = threading.Lock()

# =========================================================
# 🧠 Model Loader
# =========================================================
def load_nlp_models():
    """Load spaCy + sentence-transformers models safely (lazy, thread-safe)."""
    global _nlp, _model, _matcher
    with MODEL_LOAD_LOCK:
        try:
            if _nlp is None:
                _nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger"])
                logger.info("✅ spaCy model loaded.")

            if _model is None:
                _model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("✅ Sentence-transformer model loaded.")

            if _matcher is None:
                _matcher = Matcher(_nlp.vocab)
                _matcher.add("SUSPICIOUS_PATTERN", [
                    [{"LOWER": {"IN": ["fake", "staged", "ghost", "exaggerated"]}}],
                    [{"LOWER": "quick"}, {"LOWER": "cash"}],
                    [{"ENT_TYPE": "DATE"}, {"LOWER": "injury"}],
                ])
                logger.debug("✅ spaCy matcher patterns initialized.")

        except Exception as e:
            logger.error(f"❌ Error loading NLP models: {e}")

# =========================================================
# 🔍 Text Analysis Function
# =========================================================
def analyze_text(text: str, past_texts: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Analyze claim notes for fraud indicators.
    """
    if not text or not text.strip():
        return {
            "suspicious_phrases": [],
            "entities": {},
            "keyword_count": 0,
            "similarity_scores": [],
            "sentiment": 0.0,
            "is_suspicious": False
        }

    load_nlp_models()
    cache_key = f"nlp:{hash(text)}"
    cached = cache_get(cache_key)
    if cached:
        logger.debug("🧠 Cache hit for text analysis.")
        return cached

    # spaCy processing
    doc = _nlp(text.lower())

    # 1️⃣ Suspicious phrases
    suspicious_phrases = [kw for kw in SUSPICIOUS_PHRASES if kw in text.lower()]
    for match_id, start, end in _matcher(doc):
        phrase = doc[start:end].text
        if phrase not in suspicious_phrases:
            suspicious_phrases.append(phrase)
    keyword_count = len(suspicious_phrases)

    # 2️⃣ Entity extraction
    entities: Dict[str, List[str]] = {}
    for ent in doc.ents:
        entities.setdefault(ent.label_, []).append(ent.text)

    # Add money pattern
    money_matches = re.findall(r'\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?', text)
    if money_matches:
        entities.setdefault("MONEY", []).extend(money_matches)

    # 3️⃣ Similarity detection (duplicate check)
    similarity_scores = []
    max_similarity = 0.0
    if past_texts and _model:
        try:
            query_embedding = _model.encode(text)
            for prev in past_texts:
                if not prev.strip():
                    continue
                prev_emb = _model.encode(prev)
                sim = util.cos_sim(query_embedding, prev_emb)[0][0].item()
                similarity_scores.append(round(sim, 3))
            max_similarity = max(similarity_scores) if similarity_scores else 0.0
        except Exception as e:
            logger.warning(f"⚠️ Similarity check failed: {e}")

    # 4️⃣ Sentiment analysis
    sentiment = TextBlob(text).sentiment.polarity

    # 5️⃣ Determine suspiciousness
    is_suspicious = (
        keyword_count > 0
        or max_similarity > config.SIMILARITY_THRESHOLD
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
    logger.debug(f"🧩 NLP Analysis: {keyword_count} keywords, sim={max_similarity:.2f}, sent={sentiment:.2f}")
    return result

# =========================================================
# 🔗 Similarity Utility
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
        logger.warning(f"⚠️ Similarity computation error: {e}")
        return 0.0

# =========================================================
# 🧪 Local Test
# =========================================================
if __name__ == "__main__":
    test_text = "I had a staged accident to get quick cash. Injury on 2023-10-01. Amount $15000."
    prev_texts = ["Genuine accident on 2023-09-01 with Dr. Smith, $5000."]
    results = analyze_text(test_text, prev_texts)
    print("Results:\n", results)
    print("\nSimilarity:", get_text_similarity(test_text, prev_texts[0]))
