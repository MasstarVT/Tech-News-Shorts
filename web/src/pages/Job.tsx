import {icons, ArrowDown, ArrowLeft, ArrowUp, ChevronDown, ChevronRight, ExternalLink, Plus, Trash2, TriangleAlert} from "lucide-react";
import React, {useEffect, useMemo, useRef, useState} from "react";
import {api, type JobDetail, type Scene, type Script, type StageName, type Style, type Visual, type VisualType} from "../api";
import {useRoom} from "../App";
import {Field, Light, Monitor, stageStates, statusText} from "../components/ui";
import {ago, estimateSeconds, tcf, useLoad} from "../lib";

const TYPE_LABEL: Record<VisualType, string> = {
  headline: "Headline",
  stat: "Stat",
  icon: "Icon",
  versus: "Versus",
  bullets: "Bullets",
  outro: "Outro",
};

const blankVisual = (type: VisualType, from?: Visual): Visual => ({
  type,
  text: from?.text ?? "",
  tag: "",
  value: "",
  label: from?.label ?? "",
  trend: "none",
  icon: from?.icon || "news",
  left: "",
  right: "",
  items: type === "bullets" ? (from?.items.length ? from.items : ["", ""]) : (from?.items ?? []),
});

/** One line saying what the scene shows on screen. */
const onScreen = (v: Visual) => {
  switch (v.type) {
    case "headline":
      return {main: v.text, sub: v.tag ? `Tag: ${v.tag}` : ""};
    case "stat":
      return {main: `${v.value}${v.trend !== "none" ? (v.trend === "up" ? " ↑" : " ↓") : ""}`, sub: v.label};
    case "icon":
      return {main: v.text, sub: `Icon: ${v.icon}`};
    case "versus":
      return {main: `${v.left} vs ${v.right}`, sub: v.label};
    case "bullets":
      return {main: v.items.filter(Boolean).join(" · "), sub: ""};
    default:
      return {main: v.text, sub: "Closing card"};
  }
};

const LucideByName: React.FC<{name: string; size?: number}> = ({name, size = 18}) => {
  const Icon = (icons as Record<string, React.ComponentType<{size?: number; strokeWidth?: number}>>)[name];
  return Icon ? <Icon size={size} strokeWidth={1.8} /> : null;
};

/** Numbers in the article, marked so facts are quick to check against the script. */
const MarkedText: React.FC<{text: string}> = ({text}) => {
  const parts = text.slice(0, 8000).split(/(\$?\d[\d,.]*\s?(?:%|[KMB]\b|billion|million)?)/g);
  return (
    <>
      {parts.map((p, k) => (k % 2 ? <mark key={k}>{p}</mark> : <React.Fragment key={k}>{p}</React.Fragment>))}
      {text.length > 8000 ? "…" : null}
    </>
  );
};

const VisualEditor: React.FC<{
  v: Visual;
  limits: Record<string, number>;
  icons: Record<string, string>;
  onChange: (patch: Partial<Visual>) => void;
}> = ({v, limits: L, icons: iconMap, onChange}) => {
  switch (v.type) {
    case "headline":
      return (
        <div className="grid2">
          <Field label="Headline" value={v.text} limit={L.headline} onChange={(text) => onChange({text})} />
          <Field label="Tag (first scene only)" value={v.tag} limit={L.tag} onChange={(tag) => onChange({tag})} />
        </div>
      );
    case "stat":
      return (
        <div className="grid2">
          <Field label="Number" value={v.value} limit={L.stat_value} onChange={(value) => onChange({value})} help="Must appear in the article, e.g. $5B or 40%" />
          <Field label="Label" value={v.label} limit={L.stat_label} onChange={(label) => onChange({label})} />
          <div className="field">
            <label className="label" htmlFor={`trend-${v.value}`}>
              Trend arrow
            </label>
            <select id={`trend-${v.value}`} value={v.trend} onChange={(e) => onChange({trend: e.target.value as Visual["trend"]})}>
              <option value="none">None</option>
              <option value="up">Up</option>
              <option value="down">Down</option>
            </select>
          </div>
        </div>
      );
    case "icon":
      return (
        <div className="grid2">
          <div className="field">
            <label className="label" htmlFor="icon-pick">
              Icon
            </label>
            <div className="icon-pick">
              <span className="preview">
                <LucideByName name={iconMap[v.icon] ?? ""} />
              </span>
              <select id="icon-pick" value={v.icon} onChange={(e) => onChange({icon: e.target.value})}>
                {Object.keys(iconMap).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <Field label="Caption" value={v.text} limit={L.icon_text} onChange={(text) => onChange({text})} />
        </div>
      );
    case "versus":
      return (
        <div className="grid2">
          <Field label="Left" value={v.left} limit={L.versus_side} onChange={(left) => onChange({left})} />
          <Field label="Right" value={v.right} limit={L.versus_side} onChange={(right) => onChange({right})} />
          <Field label="Label under it" value={v.label} limit={L.versus_label} onChange={(label) => onChange({label})} />
        </div>
      );
    case "bullets":
      return (
        <div style={{display: "grid", gap: 10}}>
          {v.items.map((item, k) => (
            <div key={k} className="row" style={{flexWrap: "nowrap", alignItems: "end"}}>
              <div style={{flex: 1}}>
                <Field label={`Point ${k + 1}`} value={item} limit={L.bullet} onChange={(t) => onChange({items: v.items.map((x, j) => (j === k ? t : x))})} />
              </div>
              <button
                className="btn quiet"
                aria-label={`Remove point ${k + 1}`}
                disabled={v.items.length <= 2}
                onClick={() => onChange({items: v.items.filter((_, j) => j !== k)})}
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
          {v.items.length < L.bullets ? (
            <button className="btn small" style={{justifySelf: "start"}} onClick={() => onChange({items: [...v.items, ""]})}>
              <Plus size={14} /> Add point
            </button>
          ) : null}
        </div>
      );
    default:
      return <Field label="Closing line" value={v.text} onChange={(text) => onChange({text})} />;
  }
};

export const JobPage: React.FC<{id: string}> = ({id}) => {
  const {meta, tasks, version, refreshTasks} = useRoom();
  const job = useLoad(() => api.job(id), [id, version]);
  const settings = useLoad(api.settings);
  const [draft, setDraft] = useState<Script | null>(null);
  const [dirty, setDirty] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const [now, setNow] = useState(0);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [style, setStyle] = useState<Style | "">("");
  const [voice, setVoice] = useState("");
  const [videoName, setVideoName] = useState("video.mp4");
  const [targets, setTargets] = useState<string[] | null>(null);
  const [dryRun, setDryRun] = useState(false);
  const [fullArticle, setFullArticle] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const j: JobDetail | null = job.data;
  useEffect(() => {
    if (j?.script && !dirty) setDraft(structuredClone(j.script));
  }, [j]);
  useEffect(() => {
    if (meta && targets === null) setTargets(meta.targets.filter((t) => t.enabled).map((t) => t.platform));
  }, [meta, targets]);

  const cur = tasks?.current ?? null;
  const publishing = Boolean(cur && cur.job_id === id && cur.kind === "publish");
  const busy = Boolean(j?.busy || (cur && cur.job_id === id) || tasks?.queue.some((t) => t.job_id === id));

  const fps = j?.fps ?? 30;
  // Everything is counted in frames, so starts, lengths, back-time and the run time always add up.
  const durations = useMemo(() => {
    if (!draft) return [];
    return draft.scenes.map((s, k) => {
      const saved = j?.script?.scenes[k];
      const voiced = j?.voice?.scenes[k];
      const real = voiced && saved && saved.narration === s.narration && !j?.stale.voice;
      return {frames: real ? voiced.frames : Math.round(estimateSeconds(s.narration) * fps), estimated: !real};
    });
  }, [draft, j, fps]);
  const starts = useMemo(() => {
    let acc = 0;
    return durations.map((d) => {
      const s = acc;
      acc += d.frames;
      return s;
    });
  }, [durations]);
  const total = durations.reduce((a, d) => a + d.frames, 0);
  const nowF = now * fps;
  const playing = Boolean(videoRef.current && !videoRef.current.paused);
  const onAir = playing ? starts.findIndex((s, k) => nowF >= s && nowF < s + durations[k].frames) : -1;

  if (job.error && !j) return <p className="error-text">{job.error}</p>;
  if (!j || !meta) return <p className="faint">Loading the rundown…</p>;

  const lights = stageStates(j, cur);
  const videos = j.videos;
  const shown = videos.find((v) => v.name === videoName) ?? videos.find((v) => v.name === "video.mp4") ?? null;

  const patchScene = (k: number, patch: Partial<Scene>) => {
    setDraft((d) => (d ? {...d, scenes: d.scenes.map((s, i) => (i === k ? {...s, ...patch} : s))} : d));
    setDirty(true);
  };
  const patchVisual = (k: number, patch: Partial<Visual>) => {
    setDraft((d) => (d ? {...d, scenes: d.scenes.map((s, i) => (i === k ? {...s, visual: {...s.visual, ...patch}} : s))} : d));
    setDirty(true);
  };
  const moveScene = (k: number, by: number) => {
    setDraft((d) => {
      if (!d) return d;
      const scenes = [...d.scenes];
      const [s] = scenes.splice(k, 1);
      scenes.splice(k + by, 0, s);
      return {...d, scenes};
    });
    setOpen(k + by);
    setDirty(true);
  };
  const removeScene = (k: number) => {
    setDraft((d) => (d ? {...d, scenes: d.scenes.filter((_, i) => i !== k)} : d));
    setOpen(null);
    setDirty(true);
  };
  const addScene = (k: number) => {
    setDraft((d) => {
      if (!d) return d;
      const scenes = [...d.scenes];
      scenes.splice(k + 1, 0, {id: "", narration: "", visual: blankVisual("headline")});
      return {...d, scenes};
    });
    setOpen(k + 1);
    setDirty(true);
  };

  const act = async (fn: () => Promise<unknown>) => {
    setError("");
    try {
      await fn();
      refreshTasks();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const run = (stages: StageName[]) =>
    act(() => api.run(id, {stages, style: style || undefined, voice: voice || undefined}));

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setError("");
    try {
      const fresh = await api.saveScript(id, draft);
      setDirty(false);
      job.setData(fresh);
      if (fresh.script) setDraft(structuredClone(fresh.script));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const updateNeeds: StageName[] = j.stale.voice || !j.voice ? ["voice", "render"] : j.stale.render || !j.video ? ["render"] : [];
  const published = Object.entries(j.published);
  const seek = (k: number) => {
    setOpen(k);
    if (videoRef.current) {
      videoRef.current.currentTime = starts[k] / fps + 0.05;
    }
  };

  return (
    <>
      <div className="page-head">
        <div style={{minWidth: 0}}>
          <a href="#/jobs" className="btn quiet small" style={{marginLeft: -10, marginBottom: 8}}>
            <ArrowLeft size={14} /> Jobs
          </a>
          <h1>{draft?.title ?? j.title}</h1>
          <p>
            {j.source || "Your article"} · made {ago(j.created)} · <span className="status-word">{statusText(j, cur)}</span>
          </p>
        </div>
      </div>

      {j.held ? (
        <div className="banner standby" style={{marginBottom: 20}}>
          <span className="msg">Auto mode made this short and held it for you. Watch it, fix anything, then approve or reject it.</span>
          <button className="btn primary small" disabled={busy || !j.video} onClick={() => void act(() => api.publish(id, {targets: targets ?? undefined, dry_run: dryRun}))}>
            Approve and publish
          </button>
          <button className="btn small" disabled={busy} onClick={() => void act(() => api.reject(id).then(() => job.reload()))}>
            Reject
          </button>
        </div>
      ) : null}
      {j.status === "failed" && j.error ? (
        <div className="banner live" style={{marginBottom: 20}}>
          <span className="msg">
            <strong>The last run failed.</strong> {j.error}
          </span>
        </div>
      ) : null}
      {error ? (
        <div className="banner live" role="alert" style={{marginBottom: 20}}>
          <span className="msg">{error}</span>
        </div>
      ) : null}

      <div className="stagebar">
        <div className="stage">
          <span className="name">
            <Light s={lights.script} /> Script
          </span>
          <span className="state">{j.script ? `${draft?.scenes.length ?? 0} scenes · ${j.script.llm || "edited"}` : "Not written yet"}</span>
          <div className="ctl">
            <button
              className="btn small"
              disabled={busy}
              onClick={() => {
                if (window.confirm("Write a new script with the AI? It replaces the current script, including your edits.")) void run(["script"]);
              }}
            >
              Rewrite with AI
            </button>
          </div>
        </div>
        <div className="stage">
          <span className="name">
            <Light s={lights.voice} /> Voice
          </span>
          <span className="state">
            {j.voice ? (j.stale.voice ? "Out of date: narration changed" : `${j.voice.voice} · ${tcf(j.frames, fps)}${j.voice.timed ? "" : " · estimated timing"}`) : "Not recorded"}
          </span>
          <div className="ctl">
            <select aria-label="Voice" value={voice} onChange={(e) => setVoice(e.target.value)}>
              <option value="">{j.voice?.voice ?? meta.defaults.voice} (current)</option>
              {(settings.data?.options.voices ?? []).map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
            <button className="btn small" disabled={busy || !j.script} onClick={() => void run(["voice"])}>
              Re-record
            </button>
          </div>
        </div>
        <div className="stage">
          <span className="name">
            <Light s={lights.video} /> Video
          </span>
          <span className="state">{j.video ? (j.stale.render ? "Out of date: older than the script" : `${j.style ?? "blueprint"} style`) : "Not rendered"}</span>
          <div className="ctl">
            <select aria-label="Animation style" value={style} onChange={(e) => setStyle(e.target.value as Style | "")}>
              <option value="">{(j.style ?? meta.defaults.style).replace(/^./, (c) => c.toUpperCase())} (current)</option>
              {meta.styles.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/^./, (c) => c.toUpperCase())}
                </option>
              ))}
            </select>
            <button className="btn small" disabled={busy || !j.voice || j.stale.voice} onClick={() => void run(["render"])}>
              Render
            </button>
          </div>
        </div>
        <div className="go">
          <button className="btn primary" disabled={busy || dirty || updateNeeds.length === 0} onClick={() => void run(updateNeeds)}>
            {busy ? "Working…" : updateNeeds.length === 2 ? "Re-voice and render" : updateNeeds.length ? "Render" : "Up to date"}
          </button>
        </div>
      </div>

      <div className="cols job">
        <div>
          <section>
            <div className="head">
              <h2>Rundown</h2>
              <span className="note num">
                {draft?.scenes.length ?? 0} scenes · {tcf(total, fps)}
                {durations.some((d) => d.estimated) ? " (estimated)" : ""}
              </span>
            </div>
            {draft ? (
              <>
                <div className="timeline" aria-label="Scenes drawn to their length">
                  {draft.scenes.map((s, k) => (
                    <button
                      key={k}
                      data-type={s.visual.type}
                      style={{flexGrow: durations[k]?.frames ?? 1, flexBasis: 0}}
                      aria-current={onAir === k || open === k}
                      title={`${k + 1}. ${TYPE_LABEL[s.visual.type]} · ${tcf(durations[k]?.frames, fps)}`}
                      onClick={() => seek(k)}
                    >
                      {k + 1}
                    </button>
                  ))}
                  {total > 0 && now > 0 ? <span className="playhead" style={{left: `${Math.min(100, (nowF / total) * 100)}%`}} /> : null}
                </div>
                <div className="timescale">
                  <span>0:00</span>
                  <span>{tcf(total / 2, fps)}</span>
                  <span>{tcf(total, fps)}</span>
                </div>

                <div className="rundown">
                  <div className="rd-head">
                    <span>#</span>
                    <span>Segment</span>
                    <span>On screen</span>
                    <span>Narration</span>
                    <span className="r">Starts</span>
                    <span className="r">Length</span>
                    <span className="r" title="Time left in the short when this scene starts">Back</span>
                    <span />
                  </div>
                  {draft.scenes.map((s, k) => {
                    const scr = onScreen(s.visual);
                    const isOpen = open === k;
                    return (
                      <div className="scene" key={k} data-open={isOpen} data-air={onAir === k}>
                        <div
                          className="rd-row"
                          role="button"
                          tabIndex={0}
                          aria-expanded={isOpen}
                          aria-label={`Scene ${k + 1}, ${TYPE_LABEL[s.visual.type]}: ${scr.main || "empty"}. ${isOpen ? "Close" : "Edit"}`}
                          onClick={() => setOpen(isOpen ? null : k)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setOpen(isOpen ? null : k);
                            }
                          }}
                        >
                          <span className="n">
                            {onAir === k ? <Light s="live" label="On air" /> : onAir >= 0 && k === onAir + 1 ? <Light s="standby" label="Next" /> : null}
                            {k + 1}
                          </span>
                          <span className="slugcell">
                            <span className="slug" data-type={s.visual.type}>
                              {TYPE_LABEL[s.visual.type]}
                            </span>
                          </span>
                          <span className="screen">
                            {scr.main || <span className="faint">Empty</span>}
                            {scr.sub ? <small>{scr.sub}</small> : null}
                          </span>
                          <span className="narr">{s.narration || <span className="faint">No narration</span>}</span>
                          <span className="time r start">{tcf(starts[k], fps)}</span>
                          <span className="time r dur" data-est={durations[k]?.estimated} title={durations[k]?.estimated ? "Estimated until the voice is recorded again" : "Voiced length"}>
                            {durations[k]?.estimated ? "≈" : ""}
                            {tcf(durations[k]?.frames, fps)}
                          </span>
                          <span className="time r back">{tcf(total - starts[k], fps)}</span>
                          <span className="chev faint">{isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}</span>
                        </div>
                        {isOpen ? (
                          <div className="editor">
                            <Field
                              label="Narration"
                              value={s.narration}
                              multiline
                              rows={3}
                              onChange={(narration) => patchScene(k, {narration})}
                              help={`${s.narration.split(/\s+/).filter(Boolean).length} words. Numbers must come from the article.`}
                            />
                            <div className="visual">
                              <div className="field" style={{maxWidth: 260}}>
                                <label className="label" htmlFor={`type-${k}`}>
                                  Graphic
                                </label>
                                <select id={`type-${k}`} value={s.visual.type} onChange={(e) => patchScene(k, {visual: blankVisual(e.target.value as VisualType, s.visual)})}>
                                  {meta.visual_types.map((t) => (
                                    <option key={t} value={t}>
                                      {TYPE_LABEL[t]}
                                    </option>
                                  ))}
                                </select>
                              </div>
                              <VisualEditor v={s.visual} limits={meta.limits} icons={meta.icons} onChange={(p) => patchVisual(k, p)} />
                            </div>
                            <div className="scene-tools">
                              <button className="btn small" disabled={k === 0} onClick={() => moveScene(k, -1)}>
                                <ArrowUp size={14} /> Move up
                              </button>
                              <button className="btn small" disabled={k === draft.scenes.length - 1} onClick={() => moveScene(k, 1)}>
                                <ArrowDown size={14} /> Move down
                              </button>
                              <button className="btn small" disabled={draft.scenes.length >= 12} onClick={() => addScene(k)}>
                                <Plus size={14} /> Add scene below
                              </button>
                              <button className="btn quiet small" disabled={draft.scenes.length <= 1} onClick={() => removeScene(k)}>
                                <Trash2 size={14} /> Delete scene
                              </button>
                            </div>
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                  <div className="rd-foot">
                    <span>
                      Run time <b>{tcf(total, fps)}</b>
                    </span>
                    <span>
                      Words <b>{draft.scenes.reduce((n, s) => n + s.narration.split(/\s+/).filter(Boolean).length, 0)}</b>
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty" style={{marginTop: 14}}>
                <strong>No script yet</strong>
                {busy ? "It's being written now." : "Write one with the AI to start the rundown."}
              </div>
            )}
          </section>

          {draft ? (
            <section>
              <div className="head">
                <h2>Upload details</h2>
                <span className="note">Used for the YouTube title and description and the TikTok caption</span>
              </div>
              <div className="form" style={{maxWidth: "none"}}>
                <Field label="Title" value={draft.title} limit={100} onChange={(title) => (setDraft({...draft, title}), setDirty(true))} />
                <Field label="Description" value={draft.description} multiline rows={3} onChange={(description) => (setDraft({...draft, description}), setDirty(true))} />
                <Field
                  label="Hashtags"
                  value={draft.hashtags.join(" ")}
                  help="Separate with spaces, up to 6"
                  onChange={(t) => (setDraft({...draft, hashtags: t.split(/[\s,]+/).map((x) => x.replace(/^#/, ""))}), setDirty(true))}
                />
              </div>
            </section>
          ) : null}

          <section>
            <div className="head">
              <h2>Source</h2>
            </div>
            <div className="article">
              <div className="src">
                {j.story.url ? (
                  <a href={j.story.url} target="_blank" rel="noreferrer">
                    {j.story.title} <ExternalLink size={12} aria-hidden />
                  </a>
                ) : (
                  <span>{j.story.title}</span>
                )}
              </div>
              <div className="src">
                <span>{j.story.source || "Your article"}</span>
                {j.story.published ? <span>{ago(j.story.published)}</span> : null}
                {j.story.points ? <span>{j.story.points} HN points</span> : null}
                {j.story.also_in.length ? <span>Also in {j.story.also_in.join(", ")}</span> : null}
              </div>
              {j.story.text || j.story.summary ? (
                <>
                  <div className="body" data-clamped={!fullArticle && (j.story.text || j.story.summary).length > 900}>
                    <MarkedText text={j.story.text || j.story.summary} />
                  </div>
                  {(j.story.text || j.story.summary).length > 900 ? (
                    <button className="btn quiet small" style={{marginTop: 8}} onClick={() => setFullArticle((v) => !v)}>
                      {fullArticle ? "Show less" : "Show the whole article"}
                    </button>
                  ) : null}
                </>
              ) : (
                <p>Only the headline was available.</p>
              )}
            </div>
          </section>

          {j.log.length ? (
            <details className="log" style={{marginTop: 24}}>
              <summary>Run log ({j.log.length} lines)</summary>
              <pre>{j.log.join("\n")}</pre>
            </details>
          ) : null}
          {dirty ? (
            <div className="savebar" role="status">
              <span className="msg">Unsaved script changes. Saving re-checks the facts; the voice or video will then need an update.</span>
              <button
                className="btn small"
                onClick={() => {
                  setDirty(false);
                  setDraft(j.script ? structuredClone(j.script) : null);
                }}
              >
                Discard
              </button>
              <button className="btn primary small" disabled={saving || busy} onClick={() => void save()}>
                {saving ? "Saving…" : "Save script"}
              </button>
            </div>
          ) : null}
        </div>

        <aside className="side">
          <section>
            <Monitor
              src={shown?.url ?? null}
              videoRef={videoRef}
              onTime={setNow}
              empty={busy ? "Rendering…" : "Render the video to watch it here"}
            >
              {videos.length > 1 ? (
                <select aria-label="Which render" value={shown?.name ?? ""} onChange={(e) => setVideoName(e.target.value)}>
                  {videos.map((v) => (
                    <option key={v.name} value={v.name}>
                      {v.name}
                    </option>
                  ))}
                </select>
              ) : null}
              {shown ? (
                <span className="num">
                  {shown.mb} MB · {ago(shown.at)}
                </span>
              ) : null}
            </Monitor>
            {j.video && j.stale.render ? (
              <div className="banner standby" style={{marginTop: 12}}>
                <span className="msg">This video is older than the script.</span>
                <button className="btn small" disabled={busy || dirty} onClick={() => void run(updateNeeds.length ? updateNeeds : ["render"])}>
                  Update it
                </button>
              </div>
            ) : null}
          </section>

          <section>
            <div className="head">
              <h2>Fact checks</h2>
              <span className="note">{j.script?.warnings.length ? `${j.script.warnings.length} to check` : ""}</span>
            </div>
            {dirty ? <p className="okline">Save the script to re-check it.</p> : null}
            {j.script?.warnings.length ? (
              <ul className="panel-list">
                {j.script.warnings.map((w, k) => (
                  <li className="warning" key={k}>
                    <TriangleAlert size={15} aria-hidden />
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="okline">
                <Light s="ready" /> Every number in the script appears in the article.
              </p>
            )}
          </section>

          <section>
            <div className="head">
              <h2>Publish</h2>
            </div>
            <div className="targets">
              {meta.targets.map((t) => {
                const on = targets?.includes(t.platform) ?? false;
                return (
                  <label className="target" key={t.platform} style={{opacity: t.enabled ? 1 : 0.55}}>
                    <input
                      type="checkbox"
                      checked={on}
                      disabled={!t.enabled}
                      onChange={(e) => setTargets((all) => (e.target.checked ? [...(all ?? []), t.platform] : (all ?? []).filter((p) => p !== t.platform)))}
                    />
                    <span>
                      {t.platform === "export" ? "Export folder" : t.platform === "youtube" ? "YouTube Shorts" : "TikTok"}
                      <span className="sub">
                        {" "}
                        {!t.enabled
                          ? "· turn on in config"
                          : t.platform === "youtube"
                            ? `· ${t.privacy}`
                            : t.platform === "tiktok"
                              ? "· inbox draft"
                              : "· copies the video and captions"}
                      </span>
                    </span>
                    <span />
                  </label>
                );
              })}
              <label className="check" style={{fontSize: "var(--s-1)"}}>
                <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
                Dry run (record what would be posted, upload nothing)
              </label>
            </div>
            <button
              className="btn primary"
              style={{width: "100%"}}
              disabled={busy || !j.video || dirty || !(targets && targets.length)}
              onClick={() => {
                const force = j.stale.render;
                if (force && !window.confirm("The video is older than the script. Publish it anyway?")) return;
                void act(() => api.publish(id, {targets: targets ?? undefined, dry_run: dryRun, force}));
              }}
            >
              {publishing ? (
                <>
                  <Light s="live" /> Publishing…
                </>
              ) : dryRun ? (
                "Dry run"
              ) : j.stale.render ? (
                "Publish the older video"
              ) : (
                "Publish"
              )}
            </button>
            {published.length ? (
              <div className="results">
                {published.map(([platform, r]) => (
                  <div key={platform}>
                    <Light s={r.status === "published" ? "ready" : r.status === "failed" ? "failed" : "standby"} />
                    <span>{platform}</span>
                    <span className="detail">
                      {r.status === "needs_action" ? "In your TikTok inbox: open TikTok to post" : r.status.replace("_", " ")}
                      {r.url ? (
                        <>
                          {" · "}
                          <a href={r.url} target="_blank" rel="noreferrer">
                            open
                          </a>
                        </>
                      ) : null}
                      {r.error ? ` · ${r.error}` : ""}
                      {r.at ? ` · ${ago(r.at)}` : ""}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
            <p className="faint" style={{fontSize: "var(--s-1)", margin: "12px 0 0"}}>
              YouTube uploads stay private until the API project passes Google's audit. TikTok posts arrive in your TikTok inbox as drafts.
            </p>
          </section>

        </aside>
      </div>
    </>
  );
};
