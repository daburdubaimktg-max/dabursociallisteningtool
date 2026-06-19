import { palette, toneColor } from "./api";

// ---- layout primitives -----------------------------------------------------------
export function Section({ title, subtitle, children, accent }) {
  return (
    <section
      style={{
        border: `1px solid ${palette.line}`,
        borderTop: `3px solid ${accent || palette.line}`,
        borderRadius: 8,
        padding: 16,
        background: "#fff",
      }}
    >
      <h2 style={{ fontSize: 15, margin: "0 0 2px" }}>{title}</h2>
      {subtitle && (
        <p style={{ color: palette.muted, fontSize: 12, margin: "0 0 12px" }}>{subtitle}</p>
      )}
      {children}
    </section>
  );
}

function Chip({ label, color }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "1px 8px",
        borderRadius: 999,
        fontSize: 12,
        color: "#fff",
        background: color,
      }}
    >
      {label}
    </span>
  );
}

// ---- filter bar ------------------------------------------------------------------
function Select({ label, value, options, onChange }) {
  return (
    <label style={{ fontSize: 12, color: palette.muted, display: "grid", gap: 2 }}>
      {label}
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value || null)}
        style={{ padding: 6, border: `1px solid ${palette.line}`, borderRadius: 6, minWidth: 120 }}
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

export function FilterBar({ options, filters, setFilter, clear }) {
  const active = Object.values(filters).some(Boolean);
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 12,
        alignItems: "end",
        padding: 12,
        background: palette.bg,
        border: `1px solid ${palette.line}`,
        borderRadius: 8,
      }}
    >
      <Select label="Platform" value={filters.platform} options={options.platforms || []}
        onChange={(v) => setFilter("platform", v)} />
      <Select label="Brand" value={filters.brand} options={options.brands || []}
        onChange={(v) => setFilter("brand", v)} />
      <Select label="Market" value={filters.market} options={options.markets || []}
        onChange={(v) => setFilter("market", v)} />
      <Select label="Sentiment" value={filters.sentiment} options={options.sentiments || []}
        onChange={(v) => setFilter("sentiment", v)} />
      <label style={{ fontSize: 12, color: palette.muted, display: "grid", gap: 2 }}>
        From
        <input type="date" value={filters.date_from || ""}
          onChange={(e) => setFilter("date_from", e.target.value || null)}
          style={{ padding: 6, border: `1px solid ${palette.line}`, borderRadius: 6 }} />
      </label>
      <label style={{ fontSize: 12, color: palette.muted, display: "grid", gap: 2 }}>
        To
        <input type="date" value={filters.date_to || ""}
          onChange={(e) => setFilter("date_to", e.target.value || null)}
          style={{ padding: 6, border: `1px solid ${palette.line}`, borderRadius: 6 }} />
      </label>
      {active && (
        <button onClick={clear} style={{ padding: "7px 12px", cursor: "pointer" }}>
          Clear filters
        </button>
      )}
    </div>
  );
}

// ---- sentiment (kept visually distinct from reach) -------------------------------
const SENTS = ["positive", "neutral", "negative"];

export function StackedSentiment({ split, onDrill }) {
  const total = split.total || 0;
  return (
    <div>
      <div style={{ display: "flex", height: 22, borderRadius: 4, overflow: "hidden" }}>
        {SENTS.map((s) => {
          const n = split[s] || 0;
          const pct = total ? (n / total) * 100 : 0;
          if (!pct) return null;
          return (
            <div
              key={s}
              title={`${s}: ${n}`}
              onClick={() => onDrill && onDrill({ sentiment: s })}
              style={{
                width: `${pct}%`,
                background: palette[s],
                cursor: onDrill ? "pointer" : "default",
              }}
            />
          );
        })}
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 6, fontSize: 12 }}>
        {SENTS.map((s) => (
          <span key={s} style={{ color: palette[s] }}>
            ● {split[s] || 0} {s}
          </span>
        ))}
        <span style={{ color: palette.muted, marginLeft: "auto" }}>n={total}</span>
      </div>
    </div>
  );
}

export function NetScore({ split }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
      <span style={{ fontSize: 44, fontWeight: 700, color: toneColor(split.net_score) }}>
        {(split.net_score ?? 0).toFixed(2)}
      </span>
      <span style={{ color: palette.muted, fontSize: 12 }}>
        Net Sentiment = (pos − neg) ÷ total · −1…+1
      </span>
    </div>
  );
}

export function GroupedSplit({ rows, dimension, onDrill }) {
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {rows.map((r) => (
        <div key={r.key} style={{ display: "grid", gridTemplateColumns: "120px 1fr 48px", gap: 10, alignItems: "center" }}>
          <button
            onClick={() => onDrill && onDrill({ [dimension]: r.key })}
            title={`Drill to ${r.key}`}
            style={{ textAlign: "left", fontSize: 13, background: "none", border: "none", cursor: "pointer", color: palette.ink, padding: 0 }}
          >
            {r.key}
          </button>
          <StackedSentiment split={r} onDrill={(d) => onDrill && onDrill({ [dimension]: r.key, ...d })} />
          <span style={{ fontSize: 13, fontWeight: 600, color: toneColor(r.net_score), textAlign: "right" }}>
            {r.net_score.toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function TrendChart({ points }) {
  if (!points.length) return <Empty />;
  const W = 520, H = 120, pad = 24, mid = H / 2;
  const step = points.length > 1 ? (W - pad * 2) / (points.length - 1) : 0;
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ maxWidth: W }}>
      <line x1={pad} y1={mid} x2={W - pad} y2={mid} stroke={palette.line} />
      {points.map((p, i) => {
        const x = pad + i * step;
        const h = Math.abs(p.net_score) * (mid - 10);
        const y = p.net_score >= 0 ? mid - h : mid;
        return (
          <g key={p.date}>
            <rect x={x - 6} y={y} width={12} height={h || 1}
              fill={toneColor(p.net_score)}>
              <title>{`${p.date}: net ${p.net_score.toFixed(2)} (n=${p.total})`}</title>
            </rect>
            <text x={x} y={H - 4} fontSize="9" textAnchor="middle" fill={palette.muted}>
              {p.date.slice(5)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ---- reach views (distinct hue, never blended with sentiment) --------------------
export function VolumeCards({ volume }) {
  const e = volume.engagement || {};
  const cards = [
    ["Posts", volume.posts],
    ["Comments", volume.comments],
    ["Likes", e.likes],
    ["Views", e.views],
    ["Shares", e.shares],
    ["Saves", e.saves],
  ];
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
      {cards.map(([label, v]) => (
        <div key={label} style={{ border: `1px solid ${palette.line}`, borderRadius: 6, padding: "8px 14px", minWidth: 90 }}>
          <div style={{ fontSize: 11, color: palette.muted }}>{label}</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: palette.reach }}>
            {v == null ? "—" : v.toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  );
}

export function BarList({ rows, labelKey, valueKey, color, onDrill, dimension, format }) {
  if (!rows.length) return <Empty />;
  const max = Math.max(...rows.map((r) => r[valueKey])) || 1;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {rows.map((r) => (
        <div key={r[labelKey]} style={{ display: "grid", gridTemplateColumns: "130px 1fr 64px", gap: 8, alignItems: "center" }}>
          <button
            disabled={!onDrill}
            onClick={() => onDrill && onDrill({ [dimension]: r[labelKey] })}
            style={{ textAlign: "left", fontSize: 13, background: "none", border: "none", padding: 0, color: palette.ink, cursor: onDrill ? "pointer" : "default" }}
          >
            {r[labelKey]}
          </button>
          <div style={{ background: palette.bg, borderRadius: 4 }}>
            <div style={{ width: `${(r[valueKey] / max) * 100}%`, height: 14, background: color || palette.reach, borderRadius: 4 }} />
          </div>
          <span style={{ fontSize: 12, textAlign: "right", color: palette.muted }}>
            {format ? format(r[valueKey]) : r[valueKey]}
          </span>
        </div>
      ))}
    </div>
  );
}

export function LanguageDistribution({ data }) {
  return (
    <div>
      <div style={{ marginBottom: 10, fontSize: 13 }}>
        Arabizi share:{" "}
        <strong style={{ color: palette.reach }}>
          {(data.arabizi_share * 100).toFixed(0)}%
        </strong>{" "}
        <span style={{ color: palette.muted }}>
          (Latin-script Arabic — scored in-language, not as English)
        </span>
      </div>
      <BarList rows={data.distribution} labelKey="language" valueKey="count" color={palette.reach}
        format={(v) => v} />
    </div>
  );
}

export function AuthorsTable({ authors }) {
  if (!authors.length) return <Empty />;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        <tr style={{ textAlign: "left", color: palette.muted, fontSize: 11 }}>
          <th style={{ padding: "4px 6px" }}>Author</th>
          <th style={{ padding: "4px 6px" }}>Comments</th>
          <th style={{ padding: "4px 6px" }}>Total likes (reach)</th>
        </tr>
      </thead>
      <tbody>
        {authors.map((a) => (
          <tr key={a.author} style={{ borderTop: `1px solid ${palette.line}` }}>
            <td style={{ padding: "4px 6px" }}>@{a.author}</td>
            <td style={{ padding: "4px 6px" }}>{a.comments}</td>
            <td style={{ padding: "4px 6px", color: palette.reach }}>{a.total_likes.toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---- word cloud ------------------------------------------------------------------
export function WordCloud({ cloud, segment, setSegment, onTermSelect, selectedTerm }) {
  const counts = cloud.terms.map((t) => t.count);
  const max = Math.max(...counts, 1);
  const min = Math.min(...counts, 1);
  const size = (n) => 12 + ((n - min) / (max - min || 1)) * 22;
  const color = segment === "all" ? palette.ink : palette[segment];
  return (
    <div>
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        {["all", "positive", "neutral", "negative"].map((s) => (
          <button key={s} onClick={() => setSegment(s)}
            style={{
              padding: "4px 10px", fontSize: 12, cursor: "pointer", borderRadius: 6,
              border: `1px solid ${palette.line}`,
              background: segment === s ? (s === "all" ? palette.ink : palette[s]) : "#fff",
              color: segment === s ? "#fff" : palette.ink,
            }}>
            {s}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 12px", alignItems: "baseline" }}>
        {cloud.terms.length === 0 && <Empty />}
        {cloud.terms.map((t) => (
          <span
            key={t.term}
            dir={t.rtl ? "rtl" : "ltr"}
            onClick={() => onTermSelect(t.term === selectedTerm ? null : t.term)}
            title={t.gloss ? `${t.term} — ${t.gloss}` : t.term}
            style={{
              fontSize: size(t.count),
              color: t.term === selectedTerm ? palette.reach : color,
              cursor: "pointer",
              fontFamily: t.rtl
                ? "'Noto Naskh Arabic','Amiri','Segoe UI',serif"
                : "inherit",
              textDecoration: t.term === selectedTerm ? "underline" : "none",
            }}
          >
            {t.term}
          </span>
        ))}
      </div>
      <p style={{ color: palette.muted, fontSize: 11, marginTop: 8 }}>
        Built from original-language tokens · hover for English gloss · click a term to
        drill the explorer below.
      </p>
    </div>
  );
}

// ---- post explorer (shared drill target) -----------------------------------------
export function PostExplorer({ rows, termFilter, clearTerm }) {
  const filtered = termFilter
    ? rows.filter((r) => (r.text_raw || "").toLowerCase().includes(termFilter.toLowerCase()))
    : rows;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: palette.muted, marginBottom: 8 }}>
        <span>{filtered.length} scored items</span>
        {termFilter && (
          <button onClick={clearTerm} style={{ cursor: "pointer" }}>
            term: “{termFilter}” ✕
          </button>
        )}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: palette.muted, fontSize: 11 }}>
              {["Platform", "Comment (orig + EN)", "Sentiment", "Brand", "Market", "Likes", "Author", "Conf.", "Source"].map((h) => (
                <th key={h} style={{ padding: "6px 8px", whiteSpace: "nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={`${r.platform}:${r.comment_id}`} style={{ borderTop: `1px solid ${palette.line}`, verticalAlign: "top" }}>
                <td style={{ padding: "6px 8px" }}>{r.platform}</td>
                <td style={{ padding: "6px 8px", maxWidth: 320 }}>
                  <div dir={r.language === "ar" ? "rtl" : "ltr"}>{r.text_raw}</div>
                  <div style={{ color: palette.muted, fontSize: 12 }}>{r.text_en}</div>
                </td>
                <td style={{ padding: "6px 8px" }}>
                  {r.sentiment && <Chip label={r.sentiment} color={palette[r.sentiment]} />}
                </td>
                <td style={{ padding: "6px 8px" }}>{(r.brands || []).join(", ")}</td>
                <td style={{ padding: "6px 8px" }}>{(r.markets || []).join(", ") || "—"}</td>
                <td style={{ padding: "6px 8px", color: palette.reach }}>{(r.likes || 0).toLocaleString()}</td>
                <td style={{ padding: "6px 8px" }}>@{r.author}</td>
                <td style={{ padding: "6px 8px" }}>{r.confidence != null ? r.confidence.toFixed(2) : "—"}</td>
                <td style={{ padding: "6px 8px" }}>
                  {r.url ? <a href={r.url} target="_blank" rel="noreferrer">open</a> : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Empty() {
  return <p style={{ color: palette.muted, fontSize: 13 }}>No data for the current filters.</p>;
}
