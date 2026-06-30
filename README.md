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
pytest                       # 40 tests (sentiment slice + growth dashboard)
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

## Competitor social-media growth — live Excel dashboard

A second, self-contained slice tracks **competitor follower growth** on Instagram and
TikTok and exports a multi-sheet Excel dashboard modelled on the source Master Social
Tracker. This is a **reach** dimension and is kept entirely separate from sentiment
(CLAUDE.md Rule 2 — follower counts are never blended with sentiment scores).

- `config/competitors.json` — the tracked-brand taxonomy (brand → IG/TikTok handle →
  category → region). Config-as-data, editable without a redeploy (§6).
- `config/seed_followers.json` — the recorded historical monthly follower series
  (≈2,000 snapshots) so the dashboard renders with real history out of the box.
- `adapters/profile/` — follower adapter; provider-abstracted (seed/fixture by default,
  live Apify gated on `APIFY_TOKEN`), emits normalized `FollowerSnapshot` records.
- `growth/` — snapshot models, config loader, idempotent SQLite store
  (dedup on `platform + handle + period`), and the seed/collect pipeline.
- `kpi/growth.py` — MoM growth, gain leaderboard, reach share-of-voice, and IG-vs-TikTok
  combined (separate columns, never a single fused score).
- `dashboard_export/excel.py` — builds the live workbook (Overview, Instagram, TikTok,
  Growth, Combined, By Category, By Region, and two native trend line charts).

```bash
# build the workbook from current data (and collect a fresh reading for a month)
python -m scripts.build_dashboard competitor_growth_dashboard.xlsx --period 2026-06

# or via the API
curl -X POST localhost:8000/growth/seed
curl 'localhost:8000/growth/leaderboard?platform=tiktok'
curl -OJ localhost:8000/growth/dashboard.xlsx   # downloads the live .xlsx
```

"Live" = the workbook is regenerated from the current follower store on every build,
so each new monthly collection appears as a new column. Re-running seed/collect is
idempotent (updates counts in place; no duplicate rows).

### Streamlit dashboard
An interactive web front-end over the same follower store (`streamlit_app.py`): filter
by platform / category / region / brand / month window, with KPI tiles, a growth
leaderboard, follower trend charts, the IG-vs-TikTok combined view, drill-down to the
underlying snapshots, and one-click download of the live Excel workbook / filtered CSV.

```bash
pip install -e ".[app]"           # or: pip install -r requirements.txt
streamlit run streamlit_app.py    # http://localhost:8501
```

Deployable as-is to Streamlit Community Cloud (`requirements.txt` + `streamlit_app.py`
at the repo root). Reach only — the app reads follower counts and never sentiment.

## NLP backend selection
`NLP_BACKEND=stub` (default in dev) uses the deterministic non-production stub. It is
**refused in production** (`ENV=production`). The real self-hosted transformer service
(MARBERT / CAMeLBERT / NLLB-200) slots in behind the same contract and must pass
`tests/test_nlp_contract.py`.

## Secrets
Tokens (Apify, platform APIs) come from the environment only — never code/config.
`APIFY_TOKEN` enables live TikTok collection; without it the fixture provider is used.
