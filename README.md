# Dabur MENA Social Listening & Sentiment Tool

In-house social listening and sentiment analysis for Dabur International (MENA).
Optimized for Arabic and Arabizi content. See **[CLAUDE.md](./CLAUDE.md)** for the
non-negotiables: normalized schema, adapter contract, NLP contract, KPI definitions,
and the two load-bearing rules.

## Status — Phase 1, first vertical slice

The first end-to-end path is built and tested:

> **One TikTok post URL → collect → detect language → score sentiment in-language → render Net Sentiment Score.**

No other platform or feature is implemented yet (by design — breadth comes after the
slice is green).

### What's here
- `core/schema.py` — the normalized schema (pydantic).
- `adapters/tiktok/` — TikTok adapter; fixture-first collection, live Apify gated on `APIFY_TOKEN`.
- `nlp/` — the `/detect /score /translate` contract + a **non-production stub** (`model_version="stub"`, feature-flagged).
- `pipeline/` — collect→detect→translate(display)→score(in-language)→enrich→silver→gold, idempotent.
- `kpi/net_sentiment.py` — Net Sentiment Score, computed from sentiment counts only (reach ≠ sentiment).
- `api/` — FastAPI: `POST /jobs`, `GET /kpi/net-sentiment`.
- `dashboard/` — minimal React page rendering the one KPI.

### Two load-bearing rules (enforced in code + tests)
1. **Score in language, translate for display.** Comments are scored on `text_raw`;
   `text_en` is display-only and never reaches the scorer.
2. **Reach ≠ sentiment.** The Net Sentiment functions take sentiment counts only — there
   is no engagement parameter, and a test asserts this at the signature level.

## Run it

### Backend + tests
```bash
pip install -e ".[dev]"
pytest                       # 23 tests
uvicorn api.main:app --reload   # http://localhost:8000
```

```bash
# run the slice over the bundled TikTok fixture
curl -X POST localhost:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.tiktok.com/@vatika.mena/video/7298451200000000001"}'
curl localhost:8000/kpi/net-sentiment
# -> {"positive":3,"neutral":1,"negative":1,"total":5,"net_score":0.4}
```

### Dashboard
```bash
cd dashboard && npm install && npm run dev   # proxies /api -> :8000
```

## NLP backend selection
`NLP_BACKEND=stub` (default in dev) uses the deterministic non-production stub. It is
**refused in production** (`ENV=production`).

`NLP_BACKEND=transformer` selects the real, self-hosted MARBERT-backed service
(`nlp/transformer_service.py`): language detection (Arabic-script + Arabizi heuristics,
LID model for Latin scripts) followed by **in-language** sentiment scoring (Rule 1) on a
MARBERT-family model for Arabic/Arabizi and a multilingual XLM-R model for English/Latin.
Scores are stamped `model_version="marbert:<model-id>"`. `translate` is a marked,
display-only passthrough until the NLLB-200 / GPU slice (`[mt-pending]`).

Install the (heavy) backend deps — kept out of `dev`/CI so the default suite stays
GPU-free:
```bash
pip install -e ".[transformer]"
```
Model ids are env-overridable and pinned via the registry in production:
`NLP_AR_SENTIMENT_MODEL`, `NLP_AR_MAGHREBI_SENTIMENT_MODEL`, `NLP_EN_SENTIMENT_MODEL`,
`NLP_LID_MODEL`, `NLP_AR_DIALECT_MODEL`.

Both backends satisfy the **same** contract: `tests/test_nlp_contract.py` runs its spec
over the stub and the transformer service. The transformer parameter auto-skips when the
deps/weights aren't present (e.g. CPU CI), so it validates the real service wherever it
can be exercised without breaking the lean default run.

> Accuracy/F1 against a frozen held-out MENA eval set is the production-promotion gate
> and is **deferred until we have labeled data** — the default model ids are sensible
> starting points, not yet validated for reporting.

## Secrets
Tokens (Apify, platform APIs) come from the environment only — never code/config.
`APIFY_TOKEN` enables live TikTok collection; without it the fixture provider is used.
