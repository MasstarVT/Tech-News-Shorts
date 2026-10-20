import {Radio} from "lucide-react";
import React, {useEffect, useState} from "react";
import type {JobSummary, Task, Tasks} from "../api";
import {tc, tcf} from "../lib";

export type LightState = "off" | "ready" | "standby" | "live" | "failed";

export const Light: React.FC<{s: LightState; label?: string}> = ({s, label}) => (
  <span className="light" data-s={s} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} />
);

/** Byte's head, line-drawn, with the tally on the antenna. */
export const ByteMark: React.FC<{size?: number; live?: boolean}> = ({size = 28, live}) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
    <g fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 5.5v3.5" />
      <rect x="6.5" y="9" width="19" height="15" rx="5" />
      <path d="M12.8 20h6.4" />
    </g>
    <circle cx="16" cy="4.6" r="2.2" fill={live ? "#ff4b45" : "#e5322d"} />
    <circle cx="12.5" cy="15.5" r="1.9" fill="currentColor" />
    <circle cx="19.5" cy="15.5" r="1.9" fill="currentColor" />
  </svg>
);

const useNow = (ms = 1000) => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(t);
  }, [ms]);
  return now;
};

export const Clock: React.FC = () => {
  const now = useNow();
  return (
    <time className="clock" dateTime={new Date(now).toISOString()}>
      {new Date(now).toLocaleTimeString(undefined, {hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false})}
    </time>
  );
};

export const elapsed = (task: Task | null | undefined, now: number) =>
  task?.started ? Math.max(0, (now - new Date(task.started).getTime()) / 1000) : 0;

/** OFF AIR when idle, STANDBY while queued or writing/voicing, ON AIR while rendering or publishing. */
export const Tally: React.FC<{tasks: Tasks | null}> = ({tasks}) => {
  const now = useNow();
  const cur = tasks?.current ?? null;
  const queued = tasks?.queue.length ?? 0;
  const state = cur ? (cur.live ? "live" : "standby") : queued ? "standby" : "off";
  const word = state === "live" ? "On air" : state === "standby" ? "Standby" : "Off air";
  const what = cur ? `${cur.stage || "Starting"} · ${cur.title.replace(/^[^:]+:\s*/, "")}` : queued ? `${queued} queued` : "Nothing running";
  const href = cur?.job_id ? `#/jobs/${cur.job_id}` : "#/";
  return (
    <a className="tally" data-state={state} href={href} aria-live="polite" title={cur ? `${cur.stage} - ${cur.title}` : word}>
      <Light s={state === "live" ? "live" : state === "standby" ? "standby" : "off"} />
      <span className="word">{word}</span>
      <span className="what">{what}</span>
      {cur ? <span className="elapsed">{tc(elapsed(cur, now), false)}</span> : null}
      {cur && cur.progress != null ? <span className="meter" style={{width: `${Math.round(cur.progress * 100)}%`}} /> : null}
    </a>
  );
};

/** Fact-check state: a light plus the count, the same everywhere a job appears. */
export const Checks: React.FC<{n: number; short?: boolean}> = ({n, short}) => (
  <span className="status-word" title={n ? `${n} fact or length warnings to check` : "Every number is in the article"}>
    <Light s={n ? "standby" : "ready"} />
    {short ? n : n ? `${n} to check` : "Facts check out"}
  </span>
);

export type StageStates = {script: LightState; voice: LightState; video: LightState; posted: LightState};

/** Light per pipeline stage for a job, taking a running task into account. */
export const stageStates = (j: JobSummary, cur: Task | null | undefined): StageStates => {
  const mine = cur && cur.job_id === j.id && cur.status === "running" ? cur.stage.toLowerCase() : "";
  const failed = j.status === "failed";
  const script: LightState = mine.includes("script") ? "live" : j.stages.script ? "ready" : failed ? "failed" : "off";
  const voice: LightState = mine.includes("voice")
    ? "live"
    : j.stages.voice
      ? j.stale.voice
        ? "standby"
        : "ready"
      : failed && j.stages.script
        ? "failed"
        : "off";
  const video: LightState = mine.startsWith("render")
    ? "live"
    : j.video
      ? j.stale.render
        ? "standby"
        : "ready"
      : failed && j.stages.voice
        ? "failed"
        : "off";
  const results = Object.values(j.published);
  const posted: LightState = mine.startsWith("publish")
    ? "live"
    : results.some((r) => r.status === "published" || r.status === "needs_action")
      ? "ready"
      : results.some((r) => r.status === "failed")
        ? "failed"
        : j.held
          ? "standby"
          : "off";
  return {script, voice, video, posted};
};

const STAGE_LABEL: Record<keyof StageStates, string> = {script: "Script", voice: "Voice", video: "Video", posted: "Posted"};

export const StageLights: React.FC<{states: StageStates; compact?: boolean}> = ({states, compact}) =>
  compact ? (
    <span className="lights" aria-label={Object.entries(states).map(([k, v]) => `${STAGE_LABEL[k as keyof StageStates]}: ${v}`).join(", ")}>
      {(Object.keys(STAGE_LABEL) as (keyof StageStates)[]).map((k) => (
        <Light key={k} s={states[k]} />
      ))}
    </span>
  ) : (
    <div className="stagelights">
      {(Object.keys(STAGE_LABEL) as (keyof StageStates)[]).map((k) => (
        <span key={k}>
          <Light s={states[k]} />
          {STAGE_LABEL[k]}
        </span>
      ))}
    </div>
  );

export const statusText = (j: JobSummary, cur: Task | null | undefined) => {
  if (cur && cur.job_id === j.id) return cur.stage || "Starting";
  if (j.busy) return "Queued";
  if (j.status === "failed") return "Failed";
  if (j.held) return "Waiting for approval";
  if (Object.values(j.published).some((r) => r.status === "published" || r.status === "needs_action")) return "Published";
  if (j.stale.render) return "Needs a new render";
  if (j.video) return "Ready to publish";
  return j.status.charAt(0).toUpperCase() + j.status.slice(1);
};

/** The program monitor: the video at 9:16 with a timecode readout. */
export const Monitor: React.FC<{
  src: string | null;
  label?: string;
  videoRef?: React.Ref<HTMLVideoElement>;
  onTime?: (t: number) => void;
  empty?: React.ReactNode;
  children?: React.ReactNode;
}> = ({src, label = "Program", videoRef, onTime, empty, children}) => {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  // Frame 0 of a short is nearly black (titles haven't come in yet), so an idle monitor cues a frame a moment in
  // and jumps back to the start on the first play.
  const cue = React.useRef<number | null>(null);
  return (
    <div className="monitor">
      <div className="monitor-label">
        <Light s={playing ? "live" : src ? "ready" : "off"} />
        {label}
        <span className="tc">{tcf(t * 30)}</span>
      </div>
      {src ? (
        <video
          key={src}
          ref={videoRef}
          src={src}
          controls
          playsInline
          preload="metadata"
          onLoadedData={(e) => {
            const v = e.currentTarget;
            if (v.currentTime === 0 && v.paused) {
              cue.current = Math.min(1.6, v.duration / 4);
              v.currentTime = cue.current;
            }
          }}
          onTimeUpdate={(e) => {
            const v = e.currentTarget.currentTime;
            setT(v);
            onTime?.(v);
          }}
          onPlay={(e) => {
            const v = e.currentTarget;
            if (cue.current !== null && Math.abs(v.currentTime - cue.current) < 0.05) v.currentTime = 0;
            cue.current = null;
            setPlaying(true);
          }}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
        />
      ) : (
        <div className="blank">
          <Radio size={28} strokeWidth={1.5} aria-hidden />
          {empty ?? "No video yet"}
        </div>
      )}
      {children ? <div className="monitor-foot">{children}</div> : null}
    </div>
  );
};

export const Field: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
  limit?: number;
  multiline?: boolean;
  rows?: number;
  placeholder?: string;
  help?: string;
}> = ({label, value, onChange, limit, multiline, rows = 3, placeholder, help}) => {
  const id = React.useId();
  return (
    <div className="field">
      <label className="label" htmlFor={id}>
        <span>{label}</span>
        {limit ? (
          <span className="counter" data-full={value.length >= limit}>
            {value.length}/{limit}
          </span>
        ) : null}
      </label>
      {multiline ? (
        <textarea id={id} value={value} rows={rows} maxLength={limit} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input id={id} type="text" value={value} maxLength={limit} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      )}
      {help ? <span className="help">{help}</span> : null}
    </div>
  );
};

export const Switch: React.FC<{checked: boolean; onChange: (v: boolean) => void; label: string}> = ({checked, onChange, label}) => (
  <button type="button" className="switch" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)} />
);
