import {ArrowUpRight, Link2, MessageSquare, Newspaper, RefreshCw, Rss, TrendingUp} from "lucide-react";
import React, {useState} from "react";
import {api, type Article, type Task} from "../api";
import {useRoom} from "../App";
import {Checks, Field, Light, Monitor, StageLights, elapsed, stageStates, statusText} from "../components/ui";
import {ago, tc, useLoad} from "../lib";

const QueueList: React.FC<{tasks: Task[]; current: Task | null}> = ({tasks, current}) => (
  <ul className="queue">
    {current ? (
      <li>
        <span className="light" data-s={current.live ? "live" : "standby"} />
        <div style={{minWidth: 0}}>
          <div className="t">{current.title}</div>
          <div className="sub">
            {current.stage || "Starting"}
            {current.progress != null ? ` · ${Math.round(current.progress * 100)}%` : ""} · {tc(elapsed(current, Date.now()), false)}
          </div>
          <div className="meter-bar" data-indeterminate={current.progress == null}>
            <i style={{width: `${Math.round((current.progress ?? 0) * 100)}%`}} />
          </div>
        </div>
        {current.job_id ? (
          <a className="btn small" href={`#/jobs/${current.job_id}`}>
            Open
          </a>
        ) : (
          <span />
        )}
      </li>
    ) : null}
    {tasks.map((t) => (
      <li key={t.id}>
        <Light s={t.status === "failed" ? "failed" : t.status === "done" ? "ready" : "standby"} />
        <div style={{minWidth: 0}}>
          <div className="t">{t.title}</div>
          <div className="sub">
            {t.status === "queued" ? "Queued" : t.status === "failed" ? t.error || "Failed" : `Done${t.result.seconds ? ` in ${tc(Number(t.result.seconds), false)}` : ""}`}
          </div>
        </div>
        {t.job_id ? (
          <a className="btn quiet small" href={`#/jobs/${t.job_id}`}>
            Open
          </a>
        ) : (
          <span />
        )}
      </li>
    ))}
  </ul>
);

const ARTICLE_MIN = 200; // keep in step with app.py
const BLANK: Article = {title: "", text: "", source: "", url: ""};

/** Make a short from a link, or from article text pasted in (its only source of facts). */
const OwnStory: React.FC = () => {
  const {refreshTasks} = useRoom();
  const [mode, setMode] = useState<"link" | "article">("link");
  const [link, setLink] = useState("");
  const [article, setArticle] = useState<Article>(BLANK);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [queued, setQueued] = useState("");

  const submit = async (body: {url?: string; article?: Article}) => {
    setError("");
    setQueued("");
    setBusy(true);
    try {
      const task = await api.make(body);
      refreshTasks();
      setQueued(task.title.replace(/^Make: /, ""));
      if (body.url) setLink("");
      else setArticle(BLANK);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const set = (patch: Partial<Article>) => setArticle((a) => ({...a, ...patch}));
  const missing = ARTICLE_MIN - article.text.trim().length;

  return (
    <section>
      <div className="head">
        <h2>Your own story</h2>
        <div className="actions">
          <div className="seg" role="group" aria-label="Story source">
            <button type="button" aria-pressed={mode === "link"} onClick={() => setMode("link")}>
              Link
            </button>
            <button type="button" aria-pressed={mode === "article"} onClick={() => setMode("article")}>
              Paste article
            </button>
          </div>
        </div>
      </div>
      {mode === "link" ? (
        <form
          className="linkform"
          onSubmit={(e) => {
            e.preventDefault();
            if (link.trim()) void submit({url: link.trim()});
          }}
        >
          <label className="sr" htmlFor="link">
            Article link
          </label>
          <input id="link" type="url" placeholder="Paste an article link…" value={link} onChange={(e) => setLink(e.target.value)} />
          <button className="btn" type="submit" disabled={busy || !link.trim()}>
            <Link2 size={15} />
            Make from link
          </button>
        </form>
      ) : (
        <form
          className="form"
          style={{maxWidth: "none"}}
          onSubmit={(e) => {
            e.preventDefault();
            void submit({article});
          }}
        >
          <Field label="Headline" value={article.title} onChange={(title) => set({title})} limit={200} placeholder="What happened, in one line" />
          <Field
            label="Article text"
            value={article.text}
            onChange={(text) => set({text})}
            limit={20000}
            multiline
            rows={10}
            placeholder="Paste the article or your own write-up. The script uses only the facts in this text."
          />
          <div className="grid2">
            <Field label="Source (optional)" value={article.source} onChange={(source) => set({source})} limit={60} placeholder="Outlet or author" help="Credited in the narration and the description." />
            <Field label="Link (optional)" value={article.url} onChange={(url) => set({url})} placeholder="https://…" help="Added to the video description. The page isn't read." />
          </div>
          <div className="row">
            <button className="btn primary" type="submit" disabled={busy || !article.title.trim() || missing > 0}>
              Make short
            </button>
            {article.text.trim() && missing > 0 ? <span className="dim">{missing} more characters of article text needed</span> : null}
          </div>
        </form>
      )}
      {error ? <p className="error-text">{error}</p> : null}
      {queued ? (
        <p className="okline">
          <Light s="standby" /> Queued: {queued}. Follow it under Production.
        </p>
      ) : null}
    </section>
  );
};

export const TodayPage: React.FC = () => {
  const {tasks, version, refreshTasks} = useRoom();
  const [refresh, setRefresh] = useState(0);
  const wire = useLoad(() => api.stories(refresh > 0), [refresh]);
  const jobs = useLoad(api.jobs, [version]);
  const [started, setStarted] = useState<Record<string, string>>({});
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState("");

  const make = async (body: {story_id: string}, key: string) => {
    setError("");
    try {
      await api.make(body);
      setStarted((s) => ({...s, [key]: "Queued"}));
      refreshTasks();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const latest = jobs.data?.[0];
  const cur = tasks?.current ?? null;
  const queue = [...(tasks?.queue ?? []), ...(tasks?.recent ?? []).slice(0, 5)];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Today's wire</h1>
          <p>Stories ranked by freshness, coverage and Hacker News points. Pick one to make a short, or bring your own.</p>
        </div>
      </div>
      {latest ? (
        <a className="deck-strip" href={`#/jobs/${latest.id}`}>
          <span className="label">On deck</span>
          <span className="t">{latest.title}</span>
          <StageLights states={stageStates(latest, cur)} compact />
          {latest.scenes ? <Checks n={latest.warnings} /> : null}
        </a>
      ) : null}
      <div className="cols">
        <div>
          <OwnStory />
          <section>
            <div className="head">
              <h2>Wire</h2>
              <span className="note">{wire.data ? `Checked ${ago(wire.data.fetched)}` : wire.loading ? "Reading the feeds…" : ""}</span>
              <div className="actions">
                <a className="btn quiet small" href="#/settings" title="Add or remove RSS feeds">
                  <Rss size={14} />
                  Sources
                </a>
                <button className="btn small" onClick={() => setRefresh((r) => r + 1)} disabled={wire.loading}>
                  <RefreshCw size={14} className={wire.loading ? "spin" : undefined} />
                  Refresh
                </button>
              </div>
            </div>
            {error ? <p className="error-text">{error}</p> : null}
            {wire.error ? <p className="error-text">Couldn't read the feeds: {wire.error}</p> : null}
            {wire.loading && !wire.data ? (
              <ul className="wire" aria-busy="true">
                {Array.from({length: 6}, (_, k) => (
                  <li key={k}>
                    <span className="rank">{k + 1}</span>
                    <div style={{display: "grid", gap: 8}}>
                      <div className="skeleton" style={{width: `${70 - k * 5}%`, height: 16}} />
                      <div className="skeleton" style={{width: "40%"}} />
                    </div>
                    <span />
                  </li>
                ))}
              </ul>
            ) : wire.data && wire.data.stories.length === 0 ? (
              <div className="empty">
                <strong>Nothing new on the wire</strong>
                Every fresh story has been covered already, or the feeds are unreachable. Refresh later, add feeds under Sources, or bring your own story above.
              </div>
            ) : (
              <ol className="wire">
                {(showAll ? wire.data?.stories : wire.data?.stories.slice(0, 15))?.map((s, k) => (
                  <li key={s.id} data-taken={Boolean(started[s.id])}>
                    <span className="rank">{k + 1}</span>
                    <div style={{minWidth: 0}}>
                      <a className="title" href={s.url} target="_blank" rel="noreferrer">
                        {s.title}
                      </a>
                      <div className="meta">
                        <span>
                          <Newspaper size={13} aria-hidden />
                          {s.source}
                        </span>
                        {s.published ? <span>{ago(s.published)}</span> : null}
                        {s.points ? (
                          <span title="Hacker News points">
                            <TrendingUp size={13} aria-hidden />
                            {s.points} pts
                          </span>
                        ) : null}
                        {s.comments && s.discussion_url ? (
                          <a href={s.discussion_url} target="_blank" rel="noreferrer">
                            <MessageSquare size={13} aria-hidden /> {s.comments}
                          </a>
                        ) : null}
                        {s.also_in.length ? <span title={s.also_in.join(", ")}>+{s.also_in.length} outlets</span> : null}
                      </div>
                      {s.summary ? <p className="summary">{s.summary}</p> : null}
                    </div>
                    {started[s.id] ? (
                      <span className="status-word">
                        <Light s="standby" /> {started[s.id]}
                      </span>
                    ) : (
                      <button className="btn" onClick={() => void make({story_id: s.id}, s.id)}>
                        Make short
                      </button>
                    )}
                  </li>
                ))}
              </ol>
            )}
            {wire.data && wire.data.stories.length > 15 ? (
              <button className="btn quiet small" style={{marginTop: 10}} onClick={() => setShowAll((v) => !v)}>
                {showAll ? "Show the top 15" : `Show all ${wire.data.stories.length} stories`}
              </button>
            ) : null}
          </section>
        </div>

        <aside className="side">
          <section className="ondeck">
            <div className="head">
              <h2>On deck</h2>
              {latest ? <span className="note">{ago(latest.created)}</span> : null}
            </div>
            {latest ? (
              <>
                <div style={{marginTop: 14}}>
                  <Monitor src={latest.video} empty={statusText(latest, cur)} />
                </div>
                <h3>{latest.title}</h3>
                <StageLights states={stageStates(latest, cur)} />
                {latest.held ? (
                  <div className="banner standby" style={{marginTop: 14}}>
                    <span className="msg">Auto mode made this and is waiting for your approval.</span>
                  </div>
                ) : null}
                <div className="row" style={{marginTop: 14}}>
                  <a className="btn primary" href={`#/jobs/${latest.id}`}>
                    Open rundown
                    <ArrowUpRight size={15} />
                  </a>
                  {latest.scenes ? <Checks n={latest.warnings} /> : null}
                </div>
              </>
            ) : jobs.loading && !jobs.data ? (
              <div className="skeleton" style={{marginTop: 14, height: 360, borderRadius: 8}} />
            ) : jobs.error ? (
              <p className="error-text">{jobs.error}</p>
            ) : (
              <div className="empty" style={{marginTop: 14}}>
                <strong>No shorts yet</strong>
                Press Make short on a story. Writing, voicing and rendering take about three minutes.
              </div>
            )}
          </section>
          <section>
            <div className="head">
              <h2>Production</h2>
            </div>
            {cur || queue.length ? (
              <QueueList current={cur} tasks={queue} />
            ) : (
              <p className="okline">
                <Light s="off" /> Nothing has run since the app started.
              </p>
            )}
          </section>
        </aside>
      </div>
    </>
  );
};
