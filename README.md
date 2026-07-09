# QueryLens

An AI-powered natural language interface for querying an Oracle database — ask a question in plain English, get back a validated SQL query, the results, a plain-English explanation, and relevant charts. Built during the 48-hour IADS Hackathon (2026).

## What it does

- **Natural language → SQL** — converts a plain-English question into an Oracle SQL `SELECT` query using OCI Generative AI (Cohere `command-r-plus`).
- **Retrieval-augmented semantic search** — for more open-ended, descriptive questions, generates a query embedding (Cohere `embed-english-v3`) and matches it against pre-computed product embeddings stored directly in Oracle, using a custom cosine-similarity SQL function. This keeps retrieval inside the database rather than standing up a separate vector store.
- **SQL safety validation** — every generated query is checked before it runs: only `SELECT` statements are allowed, and any `INSERT`/`UPDATE`/`DELETE`/`DROP`/`ALTER`/`CREATE`/`TRUNCATE`/`MERGE`/`GRANT`/`REVOKE` is rejected outright.
- **Plain-English SQL explanations** — breaks down what the generated SQL is doing, clause by clause, for non-technical users.
- **Multi-turn chat** — keeps conversation context so follow-up questions can build on previous ones.
- **Follow-up question suggestions** — after a query runs, suggests related questions (grouping, filtering, comparisons) to encourage further exploration.
- **In-result visualizations** — dynamic charts built from the current query's results, alongside aggregated charts summarizing the full dataset.

## My contribution

This was a team project built in a 48-hour hackathon. I worked on the frontend (the Streamlit chat + tabs interface) and the RAG/semantic search implementation — the embedding pipeline and the cosine-similarity retrieval that sits inside the SQL layer.

## Architecture

| Layer | Choice |
|---|---|
| Data | Amazon product sales data, Oracle Autonomous Database |
| SQL generation & explanations | OCI Generative AI — Cohere `command-r-plus` |
| Embeddings / semantic search | OCI Generative AI — Cohere `embed-english-v3` |
| Frontend | Streamlit |
| Safety layer | Keyword-based SQL validator, read-only by design |

## Repository structure

```
nl-query-agent/
├── README.md
├── requirements.txt
├── .env.example
├── app.py                       # main entry point
├── db.py                        # Oracle connection pool
├── populate_vectors.py          # one-time script: computes & stores product embeddings
├── ai_sql_generator.py          # NL → SQL generation + RAG semantic search
├── validator.py                 # SQL safety validation (read-only enforcement)
├── sql_explanation.py           # plain-English SQL explanations
├── chat_tab.py                  # multi-turn chat interface
├── insight_tab.py               # AI-generated result insights
├── followup_suggestions_tab.py  # follow-up question suggestions
└── charts_in_results_tab.py     # per-query and aggregated charts
```

## Data

Not included in this repo. The app expects an Oracle Autonomous Database with a product/sales table (schema referenced in `ai_sql_generator.py`) and a `PRODUCT_VECTOR_CLOB` column populated by `populate_vectors.py` for semantic search.

## Setup & running

Requires an Oracle Autonomous Database instance with OCI Generative AI access.

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your own credentials — never commit this file

# one-time: pre-compute product embeddings for semantic search
python populate_vectors.py

streamlit run app.py
```

## Tech stack

Python · Streamlit · Oracle Cloud (Autonomous Database + Generative AI) · `oracledb` · `oci` SDK · pandas

## Possible next steps

- Add automated tests for the SQL validator
- Cache repeated similarity searches instead of recomputing per query
- Extend the aggregated charts view with additional breakdowns
