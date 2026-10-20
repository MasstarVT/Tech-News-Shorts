import React from "react";
import {spring, useCurrentFrame, useVideoConfig} from "remotion";
import {DISPLAY} from "../fonts";
import {LAYOUT} from "../theme";
import type {Scene, Theme, Word} from "../types";
import {Drawn, prog} from "./Draw";

type Page = {startMs: number; endMs: number; words: Word[]};

/** Split a scene's words into short caption pages (a few words each, breaking at punctuation and pauses). */
export const paginate = (words: Word[], maxWords: number, maxChars: number): Page[] => {
  const pages: Page[] = [];
  let cur: Word[] = [];
  const flush = () => {
    if (cur.length) pages.push({startMs: cur[0].startMs, endMs: cur[cur.length - 1].endMs, words: cur});
    cur = [];
  };
  for (const w of words) {
    const chars = cur.reduce((n, x) => n + x.text.length + 1, 0) + w.text.length;
    const gap = cur.length ? w.startMs - cur[cur.length - 1].endMs : 0;
    if (cur.length && (cur.length >= maxWords || chars > maxChars || gap > 350)) flush();
    cur.push(w);
    if (/[.!?;:]["')\]]?$/.test(w.text) || (/,$/.test(w.text) && cur.length >= 2)) flush();
  }
  flush();
  return pages;
};

export const sceneIndexAt = (starts: number[], frame: number) => {
  let i = 0;
  for (let k = 0; k < starts.length; k++) {
    if (starts[k] <= frame) i = k;
  }
  return i;
};

// Highlight a word slightly before its computed start: speech onsets land ~50-100 ms before the phoneme boundary.
const LEAD_MS = 70;

const pageFontSize = (page: Page) => {
  const chars = page.words.reduce((n, w) => n + w.text.length + 1, -1);
  const longest = page.words.reduce((n, w) => Math.max(n, w.text.length), 0);
  if (chars <= 10 && longest <= 9) return 104;
  if (chars <= 14 && longest <= 11) return 92;
  if (chars <= 18 && longest <= 13) return 80;
  return 68;
};

/**
 * Byte's speech bubble. Shows the current few words of narration; the word being spoken is highlighted.
 * The bubble draws itself in once, then pops slightly on every new page.
 */
export const SpeechBubble: React.FC<{
  scenes: Scene[];
  starts: number[];
  theme: Theme;
  maxWords: number;
  maxChars: number;
}> = ({scenes, starts, theme, maxWords, maxChars}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {x, y, w, h} = LAYOUT.bubble;
  const drawP = prog(frame, 6, 18);

  const i = sceneIndexAt(starts, frame);
  const scene = scenes[i];
  const tMs = ((frame - (starts[i] ?? 0)) / fps) * 1000;
  const pages = scene ? paginate(scene.words, maxWords, maxChars) : [];
  // The first page shows as soon as the sheet starts (dimmed until spoken), the last one stays until it ends.
  let pi = pages.length ? 0 : -1;
  for (let k = 0; k < pages.length; k++) {
    if (pages[k].startMs - LEAD_MS <= tMs) pi = k;
  }
  const page = pi >= 0 ? pages[pi] : null;
  const pageStart = page ? Math.max(0, page.startMs - LEAD_MS) : 0;
  const pageFrame = page ? frame - starts[i] - Math.round(((pi === 0 ? 0 : pageStart) / 1000) * fps) : 0;
  const pop = page ? spring({frame: pageFrame, fps, config: {damping: 12, stiffness: 240, mass: 0.6}}) : 1;

  // Bubble outline with a tail pointing at Byte's mouth (left side, lower third).
  const r = 38;
  const tailY = h * 0.62;
  const path = [
    `M ${r} 0`,
    `H ${w - r}`,
    `Q ${w} 0 ${w} ${r}`,
    `V ${h - r}`,
    `Q ${w} ${h} ${w - r} ${h}`,
    `H ${r}`,
    `Q 0 ${h} 0 ${h - r}`,
    `V ${tailY + 26}`,
    `L -46 ${tailY + 6}`,
    `L 0 ${tailY - 22}`,
    `V ${r}`,
    `Q 0 0 ${r} 0`,
    "Z",
  ].join(" ");

  return (
    <div style={{position: "absolute", left: x, top: y, width: w, height: h}}>
      <svg width={w} height={h} style={{position: "absolute", inset: 0, overflow: "visible"}}>
        <g transform={`translate(${w / 2} ${h / 2}) scale(${0.97 + 0.03 * pop}) translate(${-w / 2} ${-h / 2})`}>
          <Drawn tag="path" p={drawP} attrs={{d: path, fill: theme.ink, fillOpacity: 0.88, stroke: theme.line, strokeWidth: 5, strokeLinejoin: "round"}} />
        </g>
      </svg>
      {page && drawP > 0.6 ? (
        <div
          style={{
            position: "absolute",
            inset: "18px 28px",
            display: "flex",
            flexWrap: "wrap",
            alignContent: "center",
            justifyContent: "center",
            columnGap: "0.3em",
            fontFamily: DISPLAY,
            fontWeight: 800,
            fontSize: pageFontSize(page),
            lineHeight: 1.0,
            textAlign: "center",
            transform: `scale(${0.88 + 0.12 * pop})`,
          }}
        >
          {page.words.map((word, k) => {
            const next = page.words[k + 1];
            const active = tMs >= word.startMs - LEAD_MS && (next ? tMs < next.startMs - LEAD_MS : tMs <= word.endMs + 300);
            const done = tMs >= word.startMs - LEAD_MS;
            return (
              <span
                key={k}
                style={{
                  display: "inline-block",
                  color: active ? theme.accent : theme.line,
                  opacity: done ? 1 : 0.55,
                  transform: `scale(${active ? 1.04 : 1})`,
                }}
              >
                {word.text}
              </span>
            );
          })}
        </div>
      ) : null}
    </div>
  );
};
