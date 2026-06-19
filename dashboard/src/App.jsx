import { useCallback, useEffect, useState } from "react";
import { api, palette } from "./api";
import {
  AuthorsTable,
  BarList,
  Empty,
  FilterBar,
  GroupedSplit,
  LanguageDistribution,
  NetScore,
  PostExplorer,
  Section,
  StackedSentiment,
  TrendChart,
  VolumeCards,
  WordCloud,
} from "./components";

const FILTER_KEYS = ["platform", "brand", "market", "sentiment", "date_from", "date_to"];

// Filter state lives in the URL (CLAUDE.md §7) so views are shareable/bookmarkable.
function readFiltersFromUrl() {
  const p = new URLSearchParams(window.location.search);
  const f = {};
  for (const k of FILTER_KEYS) f[k] = p.get(k) || null;
  return f;
}

function writeFiltersToUrl(filters) {
  const p = new URLSearchParams();
  for (const k of FILTER_KEYS) if (filters[k]) p.set(k, filters[k]);
  const q = p.toString();
  window.history.replaceState(null, "", q ? `?${q}` : window.location.pathname);
}

export default function App() {
  const [filters, setFilters] = useState(readFiltersFromUrl);
  const [options, setOptions] = useState({});
  const [data, setData] = useState(null);
  const [segment, setSegment] = useState("all");
  const [cloud, setCloud] = useState({ terms: [], sentiment: "all" });
  const [term, setTerm] = useState(null);
  const [error, setError] = useState(null);
  const [booting, setBooting] = useState(true);

  const setFilter = useCallback((key, value) => {
    setFilters((prev) => {
      const next = { ...prev, [key]: value };
      writeFiltersToUrl(next);
      return next;
    });
  }, []);

  const drill = useCallback((partial) => {
    setFilters((prev) => {
      const next = { ...prev, ...partial };
      writeFiltersToUrl(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    const empty = Object.fromEntries(FILTER_KEYS.map((k) => [k, null]));
    setFilters(empty);
    writeFiltersToUrl(empty);
  }, []);

  // First load: ensure the store has data (seed runs the real pipeline over recorded
  // fixtures — not mock data), then load filter options.
  useEffect(() => {
    (async () => {
      try {
        let opts = await api.filters();
        if (!opts.platforms || opts.platforms.length === 0) {
          await api.seed();
          opts = await api.filters();
        }
        setOptions(opts);
      } catch (e) {
        setError(String(e));
      } finally {
        setBooting(false);
      }
    })();
  }, []);

  // Every view refetches when filters change — all live from the API.
  useEffect(() => {
    if (booting) return;
    (async () => {
      try {
        const [volume, split, trend, sov, hashtags, authors, languages, posts] =
          await Promise.all([
            api.volume(filters),
            api.sentimentSplit(filters),
            api.trend(filters),
            api.shareOfVoice(filters),
            api.topHashtags(filters),
            api.topAuthors(filters),
            api.languageDistribution(filters),
            api.posts(filters),
          ]);
        setData({ volume, split, trend, sov, hashtags, authors, languages, posts });
        setError(null);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, [filters, booting]);

  // Word cloud refetches on its own segment toggle (+ filters).
  useEffect(() => {
    if (booting) return;
    api.wordCloud(filters, segment).then(setCloud).catch((e) => setError(String(e)));
  }, [filters, segment, booting]);

  if (booting) return <Shell><p>Loading…</p></Shell>;
  if (error) return <Shell><p style={{ color: palette.negative }}>{error}</p></Shell>;
  if (!data) return <Shell><p>Loading views…</p></Shell>;

  return (
    <Shell>
      <FilterBar options={options} filters={filters} setFilter={setFilter} clear={clear} />

      {/* ============ REACH & VOLUME — distinct hue, never fused with sentiment ===== */}
      <GroupHeading color={palette.reach}>Reach &amp; engagement</GroupHeading>
      <Grid>
        <Section title="Volume & engagement" subtitle="Reach signals — reported separately from sentiment (Rule 2)." accent={palette.reach}>
          <VolumeCards volume={data.volume} />
        </Section>
        <Section title="Share of Voice" subtitle="Brand share of conversation volume (mentions ÷ total)." accent={palette.reach}>
          <BarList rows={data.sov} labelKey="brand" valueKey="share" color={palette.reach}
            onDrill={drill} dimension="brand" format={(v) => `${(v * 100).toFixed(0)}%`} />
        </Section>
        <Section title="Top hashtags" accent={palette.reach}>
          <BarList rows={data.hashtags} labelKey="hashtag" valueKey="count" color={palette.reach} />
        </Section>
        <Section title="Top authors / influencers" subtitle="By engagement contribution (reach)." accent={palette.reach}>
          <AuthorsTable authors={data.authors} />
        </Section>
        <Section title="Language distribution" subtitle="Including Arabizi share." accent={palette.reach}>
          <LanguageDistribution data={data.languages} />
        </Section>
      </Grid>

      {/* ================= SENTIMENT — separate group, sentiment palette =========== */}
      <GroupHeading color={palette.positive}>Sentiment</GroupHeading>
      <Grid>
        <Section title="Net Sentiment & split" subtitle="(positive − negative) ÷ total — counts only." accent={palette.positive}>
          <NetScore split={data.split.overall} />
          <div style={{ marginTop: 12 }}>
            <StackedSentiment split={data.split.overall} onDrill={drill} />
          </div>
        </Section>
        <Section title="Net Sentiment over time" subtitle="Bucketed by day. Click bars for the date." accent={palette.positive}>
          <TrendChart points={data.trend} />
        </Section>
        <Section title="Sentiment by platform" accent={palette.positive}>
          <GroupedSplit rows={data.split.by_platform} dimension="platform" onDrill={drill} />
        </Section>
        <Section title="Sentiment by brand" accent={palette.positive}>
          <GroupedSplit rows={data.split.by_brand} dimension="brand" onDrill={drill} />
        </Section>
        <Section title="Sentiment by market" accent={palette.positive}>
          {data.split.by_market.length ? (
            <GroupedSplit rows={data.split.by_market} dimension="market" onDrill={drill} />
          ) : <Empty />}
        </Section>
        <Section title="Word cloud" subtitle="Sentiment-segmented · original language · EN gloss on hover." accent={palette.positive}>
          <WordCloud cloud={cloud} segment={segment} setSegment={setSegment}
            onTermSelect={setTerm} selectedTerm={term} />
        </Section>
      </Grid>

      {/* ===================== DRILL TARGET — scored post explorer ================= */}
      <GroupHeading color={palette.ink}>Post explorer</GroupHeading>
      <Section title="Scored items" subtitle="Every chart drills here. Text shown in original language with English translation." accent={palette.ink}>
        <PostExplorer rows={data.posts} termFilter={term} clearTerm={() => setTerm(null)} />
      </Section>
    </Shell>
  );
}

function Shell({ children }) {
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 1100, margin: "32px auto", padding: "0 16px", color: palette.ink, fontVariantNumeric: "tabular-nums" }}>
      <h1 style={{ fontSize: 22, marginBottom: 2 }}>Dabur MENA — Social Listening</h1>
      <p style={{ color: palette.muted, fontSize: 13, marginTop: 0 }}>
        Score-in-language · reach and sentiment reported separately · every view drills to source.
      </p>
      <div style={{ display: "grid", gap: 16 }}>{children}</div>
    </main>
  );
}

function GroupHeading({ children, color }) {
  return (
    <h2 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: 0.6, color, margin: "8px 0 -4px", borderLeft: `3px solid ${color}`, paddingLeft: 8 }}>
      {children}
    </h2>
  );
}

function Grid({ children }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
      {children}
    </div>
  );
}
