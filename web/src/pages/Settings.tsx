import {RefreshCw, Search, X} from "lucide-react";
import React, {useEffect, useState} from "react";
import {api, type Engine, type Feed, type Settings} from "../api";
import {Field, Light, Switch} from "../components/ui";
import {useLoad} from "../lib";

type Form = {style: string; captions: boolean; engine: Engine; voice: string; speed: number | null; llm_provider: string; llm_model: string; thinking: boolean; brand: string};

const ENGINES: Record<Engine, {label: string; help: string; speed?: [number, number]}> = {
  kokoro: {label: "Kokoro (fast, offline)", help: "af_heart, af_bella, am_michael and bm_george sound the most natural.", speed: [0.8, 1.4]},
  chatterbox: {
    label: "Chatterbox (expressive, your GPU)",
    help: "Install once with `technews setup-chatterbox`. To clone a voice, add a 10-20 s clip to data/voices.",
  },
  elevenlabs: {label: "ElevenLabs (most lifelike, paid)", help: "Needs ELEVENLABS_API_KEY in .env. Billed per character.", speed: [0.7, 1.2]},
};

const toForm = (s: Settings): Form => ({
  style: s.style,
  captions: s.captions,
  engine: s.engine,
  voice: s.voice,
  speed: s.speed,
  llm_provider: s.llm.provider,
  llm_model: s.llm.model,
  thinking: s.llm.effort !== "none",
  brand: s.brand,
});

/** The RSS/Atom feeds the wire reads, plus the Hacker News switch. Every change saves straight to config.yaml. */
const Sources: React.FC = () => {
  const feeds = useLoad(api.feeds);
  const [address, setAddress] = useState("");
  const [found, setFound] = useState<{url: string; name: string; entries: number} | null>(null);
  const [checking, setChecking] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const save = async (body: {feeds: Feed[]; hacker_news?: boolean}, done: string) => {
    setError("");
    setStatus("");
    try {
      feeds.setData(await api.saveFeeds(body));
      setStatus(done);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return false;
    }
  };

  const check = async () => {
    setError("");
    setStatus("");
    setFound(null);
    setChecking(true);
    try {
      setFound(await api.checkFeed(address.trim()));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  };

  const data = feeds.data;
  const dupe =
    found && data
      ? data.feeds.find((f) => f.url.toLowerCase() === found.url.toLowerCase() || f.name.toLowerCase() === found.name.trim().toLowerCase())
      : undefined;

  const add = async () => {
    if (!found || !data) return;
    const name = found.name.trim();
    if (await save({feeds: [...data.feeds, {name, url: found.url, weight: 1}]}, `Added ${name}. Its stories join the wire on the next refresh.`)) {
      setFound(null);
      setAddress("");
    }
  };

  return (
    <section>
      <div className="head">
        <h2>News sources</h2>
        {data ? <span className="note">{data.feeds.length} feeds</span> : null}
      </div>
      {feeds.error ? <p className="error-text">{feeds.error}</p> : null}
      {data ? (
        <div className="form" style={{gap: 16}}>
          {data.feeds.length ? (
            <ul className="queue">
              {data.feeds.map((f) => (
                <li key={f.url} style={{gridTemplateColumns: "minmax(0, 1fr) auto"}}>
                  <div style={{minWidth: 0}}>
                    <div className="t">
                      <strong>{f.name}</strong>
                      {f.weight !== 1 ? <span className="faint" title="Ranking weight"> · ×{f.weight}</span> : null}
                    </div>
                    <a className="sub" style={{display: "block"}} href={f.url} target="_blank" rel="noreferrer">
                      {f.url}
                    </a>
                  </div>
                  <button
                    className="btn quiet small"
                    aria-label={`Remove ${f.name}`}
                    onClick={() => void save({feeds: data.feeds.filter((x) => x.url !== f.url)}, `Removed ${f.name}`)}
                  >
                    <X size={14} />
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="faint">No feeds. {data.hacker_news ? "The wire only shows Hacker News." : "The wire stays empty until you add one."}</p>
          )}
          <div className="switch-row">
            <div className="msg">
              <strong>Hacker News front page</strong>
              <div className="dim" style={{fontSize: "var(--s-1)"}}>
                Popular links from Hacker News, ranked by points
              </div>
            </div>
            <Switch
              label="Hacker News"
              checked={data.hacker_news}
              onChange={(on) => void save({feeds: data.feeds, hacker_news: on}, on ? "Hacker News is on" : "Hacker News is off")}
            />
          </div>
          <form
            className="linkform"
            style={{marginTop: 0}}
            onSubmit={(e) => {
              e.preventDefault();
              if (address.trim()) void check();
            }}
          >
            <label className="sr" htmlFor="feed-address">
              Feed or site address
            </label>
            <input
              id="feed-address"
              type="text"
              placeholder="RSS feed or site address, e.g. theverge.com"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
            />
            <button className="btn" type="submit" disabled={checking || !address.trim()}>
              <Search size={15} className={checking ? "spin" : undefined} />
              {checking ? "Looking…" : "Find feed"}
            </button>
          </form>
          {found ? (
            <div className="switch-row" style={{display: "grid", gap: 12}}>
              <Field label="Name" value={found.name} onChange={(name) => setFound({...found, name})} limit={60} help={`${found.entries} stories in ${found.url}`} />
              {dupe ? <p className="error-text">Already in your sources as {dupe.name}.</p> : null}
              <div className="row">
                <button className="btn primary" type="button" disabled={!found.name.trim() || Boolean(dupe)} onClick={() => void add()}>
                  Add source
                </button>
                <button className="btn quiet" type="button" onClick={() => setFound(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
          {error ? <p className="error-text">{error}</p> : null}
          {status ? <span className="dim">{status}</span> : null}
        </div>
      ) : feeds.loading ? (
        <p className="faint">Loading…</p>
      ) : null}
    </section>
  );
};

export const SettingsPage: React.FC = () => {
  const settings = useLoad(api.settings);
  const health = useLoad(api.health);
  const [form, setForm] = useState<Form | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (settings.data && !form) setForm(toForm(settings.data));
  }, [settings.data, form]);

  const set = (patch: Partial<Form>) => {
    setForm((f) => (f ? {...f, ...patch} : f));
    setStatus("");
  };

  const save = async () => {
    if (!form) return;
    setError("");
    try {
      const res = await api.saveSettings({
        style: form.style as Settings["style"],
        captions: form.captions,
        engine: form.engine,
        voice: form.voice,
        speed: form.speed ?? undefined,
        llm_provider: form.llm_provider,
        llm_model: form.llm_model,
        llm_effort: form.llm_provider === "ollama" ? (form.thinking ? "" : "none") : undefined,
        brand: form.brand,
      });
      settings.setData(res);
      setForm(toForm(res));
      setStatus("Saved to config.yaml");
      void health.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const opts = settings.data?.options;
  const models = opts ? Array.from(new Set([...(form?.llm_model ? [form.llm_model] : []), ...opts.ollama_models])) : [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>Defaults for new shorts, and the news sources the wire reads. Each job can still override style and voice.</p>
        </div>
      </div>
      <div className="cols">
        <div>
          <section>
            <div className="head">
              <h2>Defaults</h2>
            </div>
            {settings.error ? <p className="error-text">{settings.error}</p> : null}
            {form && opts ? (
              <form
                className="form"
                onSubmit={(e) => {
                  e.preventDefault();
                  void save();
                }}
              >
                <div className="grid2">
                  <div className="field">
                    <label className="label" htmlFor="brand">
                      Channel name
                    </label>
                    <input id="brand" type="text" maxLength={40} value={form.brand} onChange={(e) => set({brand: e.target.value})} />
                  </div>
                  <div className="field">
                    <label className="label" htmlFor="style">
                      Animation style
                    </label>
                    <select id="style" value={form.style} onChange={(e) => set({style: e.target.value})}>
                      {opts.styles.map((s) => (
                        <option key={s} value={s}>
                          {s.replace(/^./, (c) => c.toUpperCase())}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label className="label" htmlFor="engine">
                      Voice engine
                    </label>
                    <select
                      id="engine"
                      value={form.engine}
                      onChange={(e) => {
                        const engine = e.target.value as Engine;
                        set({engine, voice: settings.data!.engines[engine].voice, speed: settings.data!.engines[engine].speed});
                      }}
                    >
                      {opts.engines.map((e) => (
                        <option key={e} value={e}>
                          {ENGINES[e].label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label className="label" htmlFor="voice">
                      Voice
                    </label>
                    <select id="voice" value={form.voice} onChange={(e) => set({voice: e.target.value})}>
                      {Array.from(new Set([form.voice, ...opts.voices[form.engine]])).map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                    <span className="help">{ENGINES[form.engine].help}</span>
                  </div>
                  {ENGINES[form.engine].speed && form.speed !== null ? (
                    <div className="field">
                      <label className="label" htmlFor="speed">
                        <span>Speaking speed</span>
                        <span className="counter">{form.speed.toFixed(2)}×</span>
                      </label>
                      <input
                        id="speed"
                        type="range"
                        min={ENGINES[form.engine].speed![0]}
                        max={ENGINES[form.engine].speed![1]}
                        step={0.05}
                        value={form.speed}
                        onChange={(e) => set({speed: Number(e.target.value)})}
                      />
                    </div>
                  ) : null}
                  <div className="field">
                    <label className="label" htmlFor="provider">
                      Script writer
                    </label>
                    <select id="provider" value={form.llm_provider} onChange={(e) => set({llm_provider: e.target.value})}>
                      {opts.providers.map((p) => (
                        <option key={p} value={p}>
                          {p === "null" ? "No AI (template script)" : p}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label className="label" htmlFor="model">
                      Model
                    </label>
                    {form.llm_provider === "ollama" && models.length ? (
                      <select id="model" value={form.llm_model} onChange={(e) => set({llm_model: e.target.value})}>
                        {models.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input id="model" type="text" value={form.llm_model} disabled={form.llm_provider === "null"} onChange={(e) => set({llm_model: e.target.value})} />
                    )}
                    {form.llm_provider === "ollama" ? <span className="help">Installed in Ollama on this machine.</span> : null}
                  </div>
                </div>
                {form.llm_provider === "ollama" ? (
                  <label className="check">
                    <input type="checkbox" checked={form.thinking} onChange={(e) => set({thinking: e.target.checked})} />
                    Let the model think first (slower; some models return nothing with it on)
                  </label>
                ) : null}
                <div className="switch-row" style={{maxWidth: 640}}>
                  <div className="msg">
                    <strong>Captions</strong>
                    <div className="dim" style={{fontSize: "var(--s-1)"}}>
                      Show the spoken words on screen
                    </div>
                  </div>
                  <Switch label="Captions" checked={form.captions} onChange={(captions) => set({captions})} />
                </div>
                {error ? <p className="error-text">{error}</p> : null}
                <div className="row">
                  <button className="btn primary" type="submit">
                    Save settings
                  </button>
                  {status ? <span className="dim">{status}</span> : null}
                </div>
              </form>
            ) : (
              <p className="faint">Loading…</p>
            )}
          </section>
          <Sources />
        </div>

        <aside className="side">
          <section>
            <div className="head">
              <h2>Health</h2>
              <div className="actions">
                <button className="btn small" onClick={() => void health.reload()} disabled={health.loading}>
                  <RefreshCw size={14} className={health.loading ? "spin" : undefined} />
                  Re-check
                </button>
              </div>
            </div>
            {health.error ? <p className="error-text">{health.error}</p> : null}
            {health.data ? (
              <ul className="checks">
                {health.data.map((c) => (
                  <li key={c.name}>
                    <Light s={c.status === "ok" ? "ready" : c.status === "off" ? "off" : c.status === "warn" ? "standby" : "failed"} label={c.status} />
                    <div>
                      <strong>{c.name}</strong>
                      <span className="dim"> · {c.detail}</span>
                      {c.fix ? <span className="fix" data-s={c.status}>{c.fix}</span> : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="faint">Checking Node, the voice model, the script writer and publishing…</p>
            )}
          </section>
        </aside>
      </div>
    </>
  );
};
