// Live API client. Every view reads from the FastAPI read-set — no mock data.
const API = "/api";

// Build a query string from the shared filter set (brand, market, platform, sentiment,
// date_from, date_to). Empty values are omitted so they don't over-constrain.
export function qs(filters, extra = {}) {
  const params = new URLSearchParams();
  const all = { ...filters, ...extra };
  for (const [k, v] of Object.entries(all)) {
    if (v !== null && v !== undefined && v !== "") params.set(k, v);
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

async function getJSON(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

export const api = {
  seed: () => fetch(`${API}/seed`, { method: "POST" }).then((r) => r.json()),
  filters: () => getJSON(`/filters`),
  volume: (f) => getJSON(`/kpi/volume${qs(f)}`),
  sentimentSplit: (f) => getJSON(`/kpi/sentiment-split${qs(f)}`),
  netSentiment: (f) => getJSON(`/kpi/net-sentiment${qs(f)}`),
  trend: (f) => getJSON(`/kpi/net-sentiment-trend${qs(f)}`),
  shareOfVoice: (f) => getJSON(`/kpi/share-of-voice${qs(f)}`),
  wordCloud: (f, segment) =>
    getJSON(`/kpi/word-cloud${qs(f, { sentiment_segment: segment })}`),
  topHashtags: (f) => getJSON(`/kpi/top-hashtags${qs(f)}`),
  topAuthors: (f) => getJSON(`/kpi/top-authors${qs(f)}`),
  languageDistribution: (f) => getJSON(`/kpi/language-distribution${qs(f)}`),
  posts: (f) => getJSON(`/posts${qs(f)}`),
};

export const palette = {
  positive: "#1a7f37",
  neutral: "#9a6700",
  negative: "#cf222e",
  reach: "#0969da", // engagement/reach is rendered in a distinct (non-sentiment) hue
  ink: "#1f2328",
  muted: "#57606a",
  line: "#d0d7de",
  bg: "#f6f8fa",
};

export function toneColor(score) {
  if (score > 0.15) return palette.positive;
  if (score < -0.15) return palette.negative;
  return palette.neutral;
}
