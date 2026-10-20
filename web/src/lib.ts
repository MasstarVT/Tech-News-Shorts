import {useCallback, useEffect, useRef, useState} from "react";

/** "0:05.2" style timecode. */
export const tc = (seconds: number | null | undefined, tenths = true) => {
  if (seconds == null || !Number.isFinite(seconds)) return "–:––";
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  const rest = s - m * 60;
  const body = tenths ? rest.toFixed(1).padStart(4, "0") : String(Math.floor(rest)).padStart(2, "0");
  return `${m}:${body}`;
};

/** Broadcast timecode from a frame count: "0:16:13" is 16 seconds and 13 frames. */
export const tcf = (frames: number | null | undefined, fps = 30) => {
  if (frames == null || !Number.isFinite(frames)) return "–:––:––";
  const f = Math.max(0, Math.round(frames));
  const total = Math.floor(f / fps);
  const m = Math.floor(total / 60);
  return `${m}:${String(total % 60).padStart(2, "0")}:${String(f % fps).padStart(2, "0")}`;
};

/** "3h ago" from an ISO date. */
export const ago = (iso: string | null | undefined) => {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (!Number.isFinite(diff)) return "";
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
};

export const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, {month: "short", day: "numeric"});

/** Rough speaking time when there is no voice yet (Kokoro at 1.15x reads about 2.9 words a second). */
export const estimateSeconds = (narration: string) => narration.split(/\s+/).filter(Boolean).length / 2.9 + 0.5;

/** Fetch on mount and whenever `deps` change; `reload` refetches; `version` from the task feed refetches too. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const reload = useCallback(async () => {
    const n = ++seq.current;
    setLoading(true);
    try {
      const value = await load();
      if (n === seq.current) {
        setData(value);
        setError("");
      }
    } catch (e) {
      if (n === seq.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (n === seq.current) setLoading(false);
    }
  }, deps);
  useEffect(() => {
    void reload();
  }, [reload]);
  return {data, setData, error, loading, reload};
}

/** Hash routes: #/, #/jobs, #/jobs/<id>, #/auto, #/settings. */
export function useRoute() {
  const read = () => window.location.hash.replace(/^#/, "") || "/";
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export const go = (path: string) => {
  window.location.hash = path;
};
