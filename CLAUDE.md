# CLAUDE.md — Dabur MENA Social Listening & Sentiment Tool

This file is the **source of truth for the agent**. It documents the non-negotiables
so they are not regressed across sessions. Keep it current. If a change contradicts
anything here, stop and reconcile this document first.

---

## 0. Two load-bearing rules (NEVER violate)

### Rule 1 — Score in language, translate for display
- **Detect language first.** Then **score sentiment in the ORIGINAL language** using a
  language/dialect-native model.
- **Translation to English is for human reading ONLY** (`text_en`). It is produced
  *after* (or independently of) sentiment scoring and is **never** fed into the
  sentiment scorer.
- Translating Arabic → English before scoring flattens dialect, idiom, negation, and
  sarcasm and tanks accuracy. Do not do it. Ever.

### Rule 2 — Reach ≠ sentiment
- **Reach/engagement signals** (likes, views, shares, saves, comment counts, follower
  base) and **sentiment signals** (label/score/confidence) are **separate dimensions**.
- **Never average, blend, or combine them into a single metric.** "Average engagement
  by sentiment" is allowed only as engagement shown *segmented by* sentiment, displayed
  side-by-side — never a single fused number.
- Every KPI must drill down to the underlying source posts/comments.

---

## 1. Normalized schema (every adapter emits exactly this)

All platform adapters normalize their output to this shared shape so the downstream
pipeline is platform-agnostic. Fields are `null` where a platform does not expose them.

```
post_id            # platform-native id; unique together with `platform`
platform           # instagram | tiktok | youtube | reddit | x
author_handle
author_id
author_follower_count
url
posted_at          # ISO 8601, UTC
collected_at       # ISO 8601, UTC — when WE collected it
source_method      # how it was collected (e.g. "apify:clockworks/tiktok-scraper", "youtube_data_api_v3")
caption_or_title   # raw text, untranslated
media_type         # image | video | text
metrics: {
  likes, comments_count, views, shares, saves   # null where unavailable
}
comments[]: {
  comment_id, author, text_raw, likes, replied_to, posted_at
}
detected_language  # ISO code or label (e.g. "ar", "en", "arabizi", "sw")
detected_dialect   # e.g. Gulf | Egyptian | Levantine | Maghrebi | MSA | Sheng | null
text_en            # translated, FOR DISPLAY ONLY (see Rule 1)
brand_tags[]       # Vatika | Dabur Amla | ORS | Fem | Hobby | Dabur Herb'l | corporate | other
market_tags[]      # UAE | KSA | Kuwait | Iraq | Egypt | Morocco | Libya | Kenya | Zambia | Ethiopia | South Africa | ...
sentiment: {
  label,           # positive | neutral | negative
  score,           # continuous
  confidence,      # 0..1
  model_version    # MUST be stamped on every scored record (see §3)
}
topics[]
hashtags[]
emojis[]
flags: {
  is_spam, is_bot_suspected, is_counterfeit_mention, is_complaint
}
```

### Storage layout — bronze → silver → gold
- **bronze** = raw API/scrape payload, immutable, kept for re-processing.
- **silver** = normalized + enriched records (the schema above).
- **gold** = aggregated KPI tables the dashboard reads.
- Never recompute from scratch when bronze can be re-run.

### Idempotency & dedup
- Collection is **incremental and deduplicated**. Dedup key = `platform + native id`
  (`post_id` for posts, `comment_id` for comments).
- Re-running a job **updates counts** and **appends new comments** without creating
  duplicates. Idempotency is an acceptance criterion, not a nicety.

---

## 2. Adapter interface contract

One platform = one adapter = one folder = one reviewable PR. Adding a platform requires
**only** a new adapter conforming to this contract — no changes to the core pipeline.

An adapter MUST:

1. **Accept** a typed `CollectRequest` describing the job:
   `{ input_type: "post_url" | "handle" | "watch", target, date_window, max_items,
      max_comments_per_post, brands, markets }`.
2. **Emit** an iterable of records conforming to the **Normalized Schema** (§1).
   Validation against the schema is enforced by a contract test every adapter must pass.
3. **Abstract the collection provider** behind itself (Apify → Bright Data → official
   API) so the provider can be swapped without touching the pipeline.
4. **Be idempotent & resilient**: retry with exponential backoff, record partial-failure
   state, never block the pipeline on one bad post, and stamp `collected_at` +
   `source_method` on every record.
5. **Read secrets from env / a secrets manager** — never from code, config, or the
   agent's context.
6. **Persist the raw payload to bronze** before/while normalizing, so silver can be
   rebuilt without re-collecting.

Pipeline order (platform-agnostic, after the adapter):
`collect → normalize → detect language → translate (cache) → score sentiment → enrich → write silver → roll up to gold`

---

## 3. NLP service contract (self-hosted) + stub governance

All language ID, Arabizi detection, sentiment, enrichment, and translation models run on
**Dabur's own infrastructure**. **No third-party inference or translation API touches
production comment data.**

The pipeline calls an internal NLP service exposing:
- `POST /detect`    → `{ language, dialect, confidence }`  (incl. Arabizi / Sheng paths)
- `POST /score`     → `{ label, score, confidence, model_version }`  (in-language; see Rule 1)
- `POST /translate` → `{ text_en }`  (display only; cache on text hash)

**Batch** comments before inference — throughput comes from batching, not bigger hardware.

### Score-in-language routing (target production behaviour)
- Arabic (MSA + Mashriqi): MARBERT / CAMeLBERT-DA / AraBERT.
- Maghrebi / Darija: DarijaBERT / DziriBERT / TunBERT (route by detected dialect).
- East Africa: AfroXLMR / AfriBERTa (Swahili well-resourced; Sheng = detect+route+grow).
- Southern Africa: lead on multilingual English; Bemba/Nyanja detect-and-defer in v1.
- English + other Latin: XLM-RoBERTa sentiment.
- Emoji-aware scoring; output `label`, continuous `score`, `confidence`.
- Tamazight/Berber, Kikuyu/Luo/Luhya, Bemba/Nyanja: **detect-and-defer** in v1.

### Stub governance (CI / no-GPU environments)
- The deterministic stub scorer used so the pipeline runs without a GPU is **non-production**.
  It MUST be **feature-flagged** and can never be the default in a production config.
- Every stub-scored record stamps `sentiment.model_version = "stub"` (or `stub-*`) so it
  is identifiable and **excludable** from any real reporting.
- A **contract/interface test** defines the `/detect`, `/score`, `/translate` behaviour.
  Both the stub and the real transformer service MUST pass it — this validates the GPU
  swap-in against the same spec.

### Model lifecycle
- Pin and version every model; store fine-tuned weights in an internal model registry.
- `model_version` is stamped on **every** scored record (audit, rollback, attribution).
- Retrain loop fed by the human-review queue; gated promotion against a frozen held-out
  MENA eval set (never ship a worse model; no per-dialect/per-brand regression).

---

## 4. KPI definitions (precise)

Filters available everywhere: brand, market, platform, date window, language, sentiment,
spam-included toggle. Every chart drills to underlying posts/comments. Spam/bot-flagged
items are excluded from headline numbers by default (toggle to include).

### Volume & reach
- **Total posts / comments collected** — by platform, brand, market, over time.
- **Total & average engagement** — likes, comments, views, shares, saves.
- **Engagement rate** = engagements ÷ reach (views or follower base). Label the
  denominator per platform (it differs).
- **Share of Voice** = a brand's mention/engagement volume ÷ total tracked.

### Sentiment
- **Sentiment split** = positive / neutral / negative counts — overall and by platform,
  brand, market.
- **Net Sentiment Score** = `(positive − negative) ÷ total`, tracked over time.
- **Sentiment by aspect** (Phase 2): scent, price, efficacy, packaging, availability,
  counterfeit.
- **Average engagement by sentiment** — engagement shown *segmented by* sentiment,
  **never blended** into a sentiment number (Rule 2).

### Conversation & voices
- Top hashtags; top topics/keywords with trend; language distribution incl. **Arabizi share**.
- **Sentiment-segmented word cloud** — built *after* scoring; toggle positive/negative/
  neutral/all; size = frequency; colour = sentiment palette; click term → drill to
  comments. Arabic + English stopword removal + Arabic normalization (strip diacritics,
  unify alef/ya); RTL-aware font; build from original-language tokens, English gloss on hover.
- Top authors / influencers by engagement contribution (+ undisclosed-collab note).
- Emerging-topic & **spike detection**: z-score on volume/engagement, windowed to recent weeks.

### ORM / actionability
- Counterfeit-mention & complaint volume over time, with deep-links to source.
- Negative-driver breakdown (top reasons behind negative sentiment).
- Scored **post explorer** table: platform, text + English translation, sentiment chip,
  brand, market, engagement, author, source link, confidence.

---

## 5. Phasing

- **Phase 1** — Instagram + TikTok (post URL + handle). Build **one full vertical slice
  first**: TikTok URL → collect → detect → score → one KPI rendered on screen, with tests,
  before adding breadth.
- **Phase 2** — YouTube + Reddit (official APIs). Aspect-based sentiment.
- **Phase 3** — X (Twitter), gated as optional/budget-dependent.

---

## 6. Compliance & governance (requirement, not afterthought)

- Log `source_method` and `collected_at` per record; respect robots/ToS; collect only
  **public** data; store no login-gated private content.
- Configurable **retention policy**.
- Secrets (Apify token, platform API keys) live in env / secrets manager — never in code,
  config, or agent context.
- Taxonomy (brand aliases, market mappings, watch terms, retention rules) is
  **config-as-data**, editable without redeploys.
- Internal team manually reviews taxonomy, compliance, and retention logic — not auto-merged.

---

## 7. Repo layout (agent-friendly monorepo)

```
adapters/    # one platform adapter per folder (tiktok/, instagram/, ...)
pipeline/    # collect → normalize → detect → translate → score → enrich → silver → gold
nlp/         # NLP service: /detect /score /translate contract; stub + (later) real models
api/         # FastAPI: dashboard data + job-control endpoints
dashboard/   # React + charting; filter state in URL
infra/       # provisioning notes (GPU inference service, etc.)
```

Tests are the guardrail: hand-labeled MENA fixtures with golden-output pipeline tests;
contract tests asserting each adapter emits valid normalized records; snapshot tests on
gold KPI rollups. Failing tests block the slice.
