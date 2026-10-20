// Types and calls for the `technews web` API (src/technews/web/app.py). Keep both sides in step.

export type VisualType = "headline" | "stat" | "icon" | "versus" | "bullets" | "outro";
export type Trend = "up" | "down" | "none";
export type Style = "blueprint" | "kinetic" | "slideshow";
export type StageName = "script" | "voice" | "render";

export type Visual = {
  type: VisualType;
  text: string;
  tag: string;
  value: string;
  label: string;
  trend: Trend;
  icon: string;
  left: string;
  right: string;
  items: string[];
};

export type Scene = {id: string; narration: string; visual: Visual};

export type Script = {
  title: string;
  topic: string;
  description: string;
  hashtags: string[];
  scenes: Scene[];
  llm: string;
  warnings: string[];
};

export type Story = {
  id: string;
  title: string;
  url: string;
  source: string;
  published: string | null;
  summary: string;
  text?: string;
  points: number;
  comments: number;
  discussion_url: string;
  also_in: string[];
  score: number;
};

export type PublishResult = {status: string; at?: string; url?: string; path?: string; error?: string};

export type JobSummary = {
  id: string;
  title: string;
  story_title: string;
  source: string;
  url: string;
  created: string;
  status: string;
  error: string;
  stages: Record<string, Record<string, unknown> & {at?: string}>;
  published: Record<string, PublishResult>;
  warnings: number;
  scenes: number;
  seconds: number | null;
  /** Exact voiced length; every timecode in the UI is derived from frames so totals agree. */
  frames: number | null;
  fps: number;
  style: Style | null;
  video: string | null;
  held: boolean;
  busy: boolean;
  stale: {voice: boolean; render: boolean};
};

export type JobDetail = JobSummary & {
  story: Story;
  script: Script | null;
  voice: {engine: string; voice: string; speed: number; timed: boolean; warnings: string[]; scenes: {id: string; seconds: number; frames: number}[]} | null;
  metadata: Record<string, unknown> | null;
  videos: {name: string; url: string; mb: number; at: string}[];
  log: string[];
};

export type Task = {
  id: string;
  kind: "make" | "run" | "publish" | "auto";
  title: string;
  job_id: string | null;
  status: "queued" | "running" | "done" | "failed";
  stage: string;
  progress: number | null;
  created: string;
  started: string | null;
  finished: string | null;
  error: string;
  result: Record<string, unknown>;
  live: boolean;
};

export type Tasks = {current: Task | null; queue: Task[]; recent: Task[]};

export type Target = {platform: "export" | "youtube" | "tiktok"; enabled: boolean; account: string; privacy: string; mode: string};

export type Meta = {
  brand: string;
  styles: Style[];
  limits: Record<string, number>;
  icons: Record<string, string>;
  visual_types: VisualType[];
  targets: Target[];
  /** speed is null for engines without a speed control (Chatterbox). */
  defaults: {style: Style; voice: string; speed: number | null};
};

export type Engine = "kokoro" | "chatterbox" | "elevenlabs";

export type Settings = {
  style: Style;
  captions: boolean;
  /** The voice engine and its voice and speed; `engines` holds each engine's own choices. */
  engine: Engine;
  voice: string;
  speed: number | null;
  engines: Record<Engine, {voice: string; speed: number | null}>;
  llm: {provider: string; model: string; effort: string | null};
  brand: string;
  options: {styles: Style[]; engines: Engine[]; voices: Record<Engine, string[]>; ollama_models: string[]; providers: string[]};
};

/** A pasted article: its text is the script writer's only source of facts. */
export type Article = {title: string; text: string; source: string; url: string};

export type Feed = {name: string; url: string; weight: number};
export type Feeds = {feeds: Feed[]; hacker_news: boolean};

export type Check = {name: string; status: "ok" | "off" | "warn" | "fail"; detail: string; fix: string};

export type AutoSettings = {enabled: boolean; time: string; mode: "hold" | "publish"; targets: string[]; dry_run: boolean};
export type Auto = {
  settings: AutoSettings;
  state: {last_run_date: string | null; last_task: string | null; last_job: string | null};
  next_run: string | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : {"Content-Type": "application/json"},
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d: {msg?: string}) => d.msg).join("; ");
    } catch {
      /* keep the status text */
    }
    if (res.status === 401) window.dispatchEvent(new Event("tn:signed-out"));
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  session: () => call<{auth_required: boolean; signed_in: boolean}>("GET", "/session"),
  login: (token: string) => call<{ok: boolean}>("POST", "/login", {token}),
  meta: () => call<Meta>("GET", "/meta"),
  tasks: () => call<Tasks>("GET", "/tasks"),
  stories: (refresh = false) => call<{fetched: string; stories: Story[]}>("GET", `/stories${refresh ? "?refresh=true" : ""}`),
  jobs: () => call<JobSummary[]>("GET", "/jobs"),
  job: (id: string) => call<JobDetail>("GET", `/jobs/${encodeURIComponent(id)}`),
  make: (body: {story_id?: string; url?: string; article?: Article}) => call<Task>("POST", "/jobs", body),
  saveScript: (id: string, script: Pick<Script, "title" | "topic" | "description" | "hashtags" | "scenes">) =>
    call<JobDetail>("PUT", `/jobs/${encodeURIComponent(id)}/script`, {
      ...script,
      scenes: script.scenes.map((s) => ({narration: s.narration, visual: s.visual})),
    }),
  run: (id: string, body: {stages: StageName[]; style?: Style; voice?: string; speed?: number}) =>
    call<Task>("POST", `/jobs/${encodeURIComponent(id)}/run`, body),
  publish: (id: string, body: {targets?: string[]; dry_run: boolean; force?: boolean}) =>
    call<Task>("POST", `/jobs/${encodeURIComponent(id)}/publish`, body),
  reject: (id: string) => call<JobSummary>("POST", `/jobs/${encodeURIComponent(id)}/reject`),
  settings: () => call<Settings>("GET", "/settings"),
  saveSettings: (body: Partial<{style: Style; captions: boolean; engine: Engine; voice: string; speed: number; llm_provider: string; llm_model: string; llm_effort: string; brand: string}>) =>
    call<Settings>("PUT", "/settings", body),
  health: () => call<Check[]>("GET", "/health"),
  feeds: () => call<Feeds>("GET", "/feeds"),
  saveFeeds: (body: {feeds: Feed[]; hacker_news?: boolean}) => call<Feeds>("PUT", "/feeds", body),
  checkFeed: (url: string) => call<{url: string; name: string; entries: number}>("POST", "/feeds/check", {url}),
  auto: () => call<Auto>("GET", "/auto"),
  saveAuto: (body: AutoSettings) => call<Auto>("PUT", "/auto", body),
  autoRunNow: () => call<Auto>("POST", "/auto/run-now"),
};
