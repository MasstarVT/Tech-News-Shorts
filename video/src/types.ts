// Props contract between the Python pipeline (src/technews/render/props.py) and the video.
// Keep both sides in sync when changing anything here.

export type Word = {
  text: string;
  /** Milliseconds from the start of the scene. */
  startMs: number;
  endMs: number;
};

export type Trend = "up" | "down" | "none";

export type Visual =
  | {type: "headline"; text: string; tag?: string}
  | {type: "stat"; value: string; label: string; trend?: Trend}
  | {type: "icon"; icon: string; text: string}
  | {type: "versus"; left: string; right: string; label?: string}
  | {type: "bullets"; items: string[]}
  | {type: "outro"; text: string};

export type Scene = {
  id: string;
  durationInFrames: number;
  /** Narration file, relative to the job folder (served as the public dir). */
  audio: string | null;
  words: Word[];
  /** Mouth openness per frame of this scene, 0..1 (from the narration loudness). */
  mouth: number[];
  visual: Visual;
};

export type Theme = {
  bg: string;
  bgDeep: string;
  line: string;
  draft: string;
  accent: string;
  alert: string;
  ink: string;
};

export type ShortProps = {
  brand: {name: string};
  story: {source: string; date: string; topic: string};
  theme: Theme;
  scenes: Scene[];
  sfx: {swish: string | null; stamp: string | null};
  music: {src: string; volume: number} | null;
  captions: {enabled: boolean; maxWords: number; maxChars: number};
};
