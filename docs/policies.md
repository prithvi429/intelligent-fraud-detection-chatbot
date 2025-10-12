# Policy Guidance System

The policy guidance system answers user questions (e.g., "What documents?") using a hybrid approach: **keyword search** (Postgres full-text) for exact matches and **semantic search** (Pinecone vector DB) for natural language queries. It provides relevant responses, required documents, and confidence scores.

## Overview
- **Purpose**: Self-service for users (e.g., claim requirements, appeals) without agent calls.
- **Input**: Query string (e.g., "Why rejected?").
- **Process**:
  1. Embed query (OpenAI/sentence-transformers).
  2. Search Pinecone (top-k similar docs) or fallback to DB.
  3. Format response + docs list.
- **Output**: GuidanceResponse (response, docs, relevance_score 0-1).
- **Data**: ~50 policy entries in DB (editable via admin).

For architecture, see [architecture.md](architecture.md).

## Policy Data Schema
Policies stored in Postgres `policies` table (see src/utils/db.py).
