import { useState } from "react";

// Minimal slice UI: run a TikTok job, render the single KPI (Net Sentiment Score).
// Reach is deliberately NOT shown fused with sentiment (Rule 2): the volume figure
// (total comments) is presented as a separate, clearly-labelled context number.

const API = "/api";
const palette = { positive: "#1a7f37", neutral: "#9a6700", negative: "#cf222e" };

function tone(score) {
  if (score > 0.15) return "positive";
  if (score < -0.15) return "negative";
  return "neutral";
}

export default function App() {
  const [url, setUrl] = useState(
    "https://www.tiktok.com/@vatika.mena/video/7298451200000000001"
  );
  const [kpi, setKpi] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function runJob() {
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const res = await fetch(`${API}/kpi/net-sentiment`);
      setKpi(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  const color = kpi ? palette[tone(kpi.net_score)] : "#57606a";

  return (
    <main
      style={{
        fontFamily: "system-ui, sans-serif",
        maxWidth: 560,
        margin: "48px auto",
        padding: "0 16px",
        fontVariantNumeric: "tabular-nums",
      }}
    >
      <h1 style={{ fontSize: 20 }}>Net Sentiment Score</h1>
      <p style={{ color: "#57606a", fontSize: 14 }}>
        TikTok post → collect → detect language → score in-language → roll up.
      </p>

      <div style={{ display: "flex", gap: 8, margin: "16px 0" }}>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          style={{ flex: 1, padding: 8, border: "1px solid #d0d7de", borderRadius: 6 }}
        />
        <button onClick={runJob} disabled={loading} style={{ padding: "8px 16px" }}>
          {loading ? "Running…" : "Run"}
        </button>
      </div>

      {error && <p style={{ color: palette.negative }}>{error}</p>}

      {kpi && (
        <section style={{ marginTop: 24 }}>
          <div style={{ fontSize: 72, fontWeight: 700, color }}>
            {kpi.net_score.toFixed(2)}
          </div>
          <div style={{ color: "#57606a", fontSize: 14 }}>
            (positive − negative) ÷ total · range −1 to +1
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 16, fontSize: 14 }}>
            <span style={{ color: palette.positive }}>▲ {kpi.positive} positive</span>
            <span style={{ color: palette.neutral }}>● {kpi.neutral} neutral</span>
            <span style={{ color: palette.negative }}>▼ {kpi.negative} negative</span>
          </div>
          <hr style={{ margin: "16px 0", border: "none", borderTop: "1px solid #eaeef2" }} />
          <div style={{ color: "#57606a", fontSize: 13 }}>
            Reach context (shown separately, never fused with sentiment):{" "}
            <strong>{kpi.total}</strong> comments scored.
          </div>
        </section>
      )}
    </main>
  );
}
