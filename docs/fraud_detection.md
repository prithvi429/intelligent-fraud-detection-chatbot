# Fraud Detection Mechanics

This document details the core fraud detection logic in the Insurance Fraud Detection Chatbot. It combines **rule-based alarms** (13 checks for red flags) with **machine learning inference** (RandomForestClassifier on SageMaker) and a **decision policy** to classify claims as Approve, Review, or Reject. The system focuses on high recall for fraud (minimize false negatives) while balancing precision to avoid unnecessary reviews.

## Overview
- **Input**: Claim data (amount, delay, notes, provider, location, etc.) from frontend/API.
- **Process**:
  1. Run 13 alarms (rules + external checks).
  2. Extract 14 ML features from alarms/results.
  3. Invoke SageMaker endpoint for fraud probability (0-100%).
  4. Apply decision policy (prob + alarm weights → final decision).
- **Output**: FraudResponse (prob, alarms list, decision, explanation).
- **Goals**: AUC >0.85, Fraud Recall >0.80 (catch 80%+ frauds), F1 >0.75 (balanced).
- **Data**: Trained on synthetic/historical claims (~20% fraud, imbalanced).

For architecture, see [architecture.md](architecture.md).

## 13 Fraud Alarms
Alarms are rule-based checks triggered by claim data. Each has a type, description, severity (low/medium/high), and evidence. They contribute to ML features (e.g., num_alarms) and decision weighting.

### Original 5 Alarms (Core Rules)
1. **Late Reporting** (`late_reporting`, medium/high)
   - Trigger: `report_delay_days > 7` (late) or >14 (very late).
   - Evidence: Days delayed.
   - Why: Fraudsters delay to fabricate evidence.
   - Severity: Medium (7-14 days), High (>14).

2. **New Bank Account** (`new_bank`, medium)
   - Trigger: `is_new_bank = true`.
   - Evidence: Bank change flag.
   - Why: Payout to new/unverified accounts risks laundering.
   - Severity: Medium (requires verification).

3. **Out-of-Network Provider** (`out_of_network_provider`, medium)
   - Trigger: Provider not in approved network (DB check or external API).
   - Evidence: Network status.
   - Why: Higher costs, potential collusion.
   - Severity: Medium.

4. **Blacklist Hit** (`blacklist_hit`, high)
   - Trigger: Provider in blacklist table (DB query).
   - Evidence: Provider name + reason (e.g., "overbilling").
   - Why: Known fraudulent providers.
   - Severity: High (auto-review).

5. **Suspicious Text Phrases** (`suspicious_text_phrases`, medium/high)
   - Trigger: Notes contain phrases like "staged", "quick cash" (spaCy matcher).
   - Evidence: Matched phrases list.
   - Why: Indicators of exaggeration/fraud.
   - Severity: Medium (1-2 phrases), High (>2).

### Additional 8 Alarms (Advanced Checks)
6. **High Claim Amount** (`high_amount`, high)
   - Trigger: `amount > 10000` or >3x avg (outlier via IQR).
   - Evidence: Threshold/avg amount.
   - Why: Large claims more fraud-prone.
   - Severity: High.

7. **Repeat Claimant** (`repeat_claimant`, medium)
   - Trigger: >3 claims in 12 months (DB query on claimant_id).
   - Evidence: Count + last claim date.
   - Why: Patterns of serial fraud.
   - Severity: Medium.

8. **Suspicious Keywords** (`suspicious_keywords`, medium)
   - Trigger: NLP (TextBlob/sentence-transformers) detects keywords (e.g., "exaggerated pain").
   - Evidence: Keyword count + sentiment score (<0 negative).
   - Why: Fraud language patterns.
   - Severity: Medium (score >0.5).

9. **Location Mismatch** (`location_mismatch`, medium/high)
   - Trigger: Distance >100 miles (Geopy between claimant location and incident).
   - Evidence: Miles + coords.
   - Why: Claims far from residence suspicious.
   - Severity: Medium (50-100mi), High (>100mi).

10. **Duplicate Claims** (`duplicate_claims`, high)
    - Trigger: Text similarity >0.8 with past notes (cosine sim via embeddings).
    - Evidence: Similarity score + similar claim ID.
    - Why: Copy-paste fraud.
    - Severity: High.

11. **Vendor Fraud Risk** (`vendor_fraud`, high)
    - Trigger: External API risk_score >0.7 or blacklist.
    - Evidence: Score + reason (e.g., "overbilling").
    - Why: Shady vendors collude.
    - Severity: High.

12. **Time Patterns** (`time_patterns`, medium)
    - Trigger: Unusual hour (e.g., 2-5 AM) or <1 day from prior claim.
    - Evidence: Timestamp + anomaly score.
    - Why: Fraud often at odd times.
    - Severity: Medium.

13. **External Mismatch** (`external_mismatch`, medium)
    - Trigger: Weather mismatch (e.g., "slippery road" on clear day via OpenWeatherMap).
    - Evidence: Condition + is_rainy flag.
    - Why: Inconsistent story.
    - Severity: Medium.

### Alarm Implementation
- **Orchestrator**: `src/fraud_engine/alarms.py` (check_all_alarms runs all, returns list).
- **Individual Checks**: `src/fraud_engine/checks/` (e.g., check_high_amount.py).
- **External**: Mocks/calls APIs (weather, vendor); fallbacks to defaults on error.
- **NLP**: spaCy for entities/phrases, sentence-transformers for similarity.
- **DB Queries**: For repeats/blacklist (Postgres).

## Machine Learning Model
- **Type**: RandomForestClassifier (sklearn, binary: fraud 0/1).
- **Features** (14, from alarms; see FraudFeatures in src/models/fraud.py):
  1. amount_normalized (amount / global avg).
  2. delay_days.
  3. is_new_bank (0/1).
  4. is_out_of_network (0/1).
  5. num_alarms (total count).
  6. high_severity_count (high alarms).
  7. repeat_count (DB query).
  8. text_similarity_score (0-1, embeddings).
  9. location_distance (miles, Geopy).
  10. time_anomaly_score (0-1, hour/pattern).
  11. suspicious_keyword_count.
  12. sentiment_score (-1 to 1, TextBlob).
  13. vendor_risk_score (0-1, API).
  14. external_mismatch_count.
- **Training**:
  - Data: Synthetic (~2000 rows, 20% fraud) or historical (anonymized).
  - Preprocess: `src/ml/preprocess.py` (clean, engineer, split 80/20, SMOTE optional).
  - Train: `src/ml/train.py` (n_estimators=100, class_weight='balanced' for imbalance).
  - Eval: `src/ml/evaluate.py` (AUC, recall_fraud >0.80, F1 weighted).
  - Save: .pkl (model + imputer/scaler) to S3.
- **Inference**: SageMaker endpoint (ml.t3.medium). Input: CSV (14 features) → Output: prob ([:,1]).
- **Hyperparams**: Tunable (RandomizedSearchCV); focus on recall.
- **Deployment**: `infra/scripts/train_and_deploy_ml.py` (train → tar.gz → S3 → endpoint).

## Decision Policy
- **Logic**: `src/fraud_engine/decision_policy.py` (get_decision).
- **Inputs**: Fraud prob (ML) + alarms (weighted by severity).
- **Weights**: High alarm = +0.3 risk, Medium = +0.15, Low = +0.05. Total_risk = prob/100 + sum(weights).
- **Thresholds**:
  - <0.3: Approve (low risk).
  - 0.3-0.7: Review (manual check).
  - >0.7: Reject (high risk).
- **Overrides**: Blacklist/high_amount → auto Reject.
- **Simple Mode**: Prob-only (for fallback if alarms fail).

## Evaluation & Monitoring
- **Metrics**: ROC-AUC (discrimination), Precision/Recall/F1 (fraud class), Confusion Matrix.
- **Imbalance**: SMOTE oversampling, class_weight='balanced'.
- **Monitoring**: CloudWatch (invocations, latency), alarms for low recall (drift detection).
- **Retraining**: Monthly on new data (cron job via Lambda).

For API usage, see [api.md](api.md). For deployment, see [deployment.md](deployment.md).