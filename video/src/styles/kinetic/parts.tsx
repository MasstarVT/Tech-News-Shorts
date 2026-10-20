import React from "react";
import {AbsoluteFill, Easing, interpolate, random, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {paginate, sceneIndexAt} from "../../components/Captions";
import {Mascot} from "../../components/Mascot";
import {DISPLAY, TEXT} from "../../fonts";
import {SAFE} from "../../theme";
import type {Scene, ShortProps, Theme, Word} from "../../types";

// Kinetic style: bold type that moves with the voice. Same props, safe zones and timings as the blueprint style.

export const K = {
  header: {y: SAFE.top, h: 110},
  progress: {y: 302, h: 8},
  stage: {x: SAFE.left, y: 340, w: SAFE.right - SAFE.left, h: 740},
  // Below y=950 everything stays left of the like/comment rail.
  captions: {x: SAFE.left, y: 1110, w: SAFE.rightRail - SAFE.left, h: 310},
};

export type Palette = {bg: string; bg2: string; text: string; dim: string; accent: string; hot: string; cool: string; ink: string};

export const palette = (t: Theme): Palette => ({
  bg: "#080C18",
  bg2: "#141B34",
  text: "#F6F8FF",
  dim: "#A9B4D6",
  accent: t.accent,
  hot: t.alert,
  cool: "#4DD8FF",
  ink: "#05070F",
});

/** One colour per scene, cycling. */
export const sceneTints = (p: Palette, n: number) => {
  const hues = [p.accent, p.cool, p.hot, "#A58BFF", "#4BE3A4"];
  return Array.from({length: n}, (_, k) => hues[k % hues.length]);
};

export const mix = (color: string, pct: number, base = "transparent") => `color-mix(in srgb, ${color} ${pct}%, ${base})`;

/** Decaying camera shake from a list of impact frames. */
export const shake = (frame: number, impacts: number[], amp = 14) => {
  let x = 0;
  let y = 0;
  for (const f of impacts) {
    const t = frame - f;
    if (t < 0 || t > 16) continue;
    const a = amp * Math.exp(-t / 3.2);
    x += a * Math.sin(t * 2.9);
    y += a * Math.cos(t * 2.3) * 0.6;
  }
  return {x, y};
};

export const LEAD_MS = 70; // same lead as the speech bubble: onsets land slightly before phoneme boundaries

const STOP = new Set(
  "a an the of to and or but in on at for by with from as is are was be it its this that these those your you we they them their our how what why who new".split(" "),
);

const norm = (w: string) => {
  const s = w.toLowerCase().replace(/['’]s$/, "").replace(/[^\p{L}\p{N}]/gu, "");
  return s.length > 3 && s.endsWith("s") ? s.slice(0, -1) : s;
};

/** Same word, allowing for endings (detect / detection) and number formats (50M / 50). */
const sameWord = (a: string, b: string) => {
  if (/\d/.test(a) || /\d/.test(b)) return a.replace(/\D/g, "") === b.replace(/\D/g, "");
  if (a === b) return true;
  const [short, long] = a.length < b.length ? [a, b] : [b, a];
  return short.length >= 5 && long.startsWith(short);
};

/**
 * Scene frames where the narration says each word of `text` (one list per word, split on spaces).
 * Stopwords and words the voice never says get an empty list.
 */
export const spokenHits = (text: string, words: Word[], fps: number): number[][] => {
  const spoken = words.flatMap((w) => {
    const f = Math.round(((w.startMs - LEAD_MS) / 1000) * fps);
    return w.text.split(/[-/–—]/).map((part) => ({t: norm(part), f}));
  });
  return text
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => {
      const t = norm(w);
      if (!t || STOP.has(t)) return [];
      return spoken.filter((s) => s.t && sameWord(t, s.t)).map((s) => s.f);
    });
};

/** 0..1 bump that peaks two frames after each hit and fades out. */
export const pulse = (frame: number, hits: number[], decay = 8) => {
  let v = 0;
  for (const f of hits) {
    const t = frame - f;
    if (t < 0 || t > decay * 5) continue;
    v = Math.max(v, t < 2 ? t / 2 : Math.exp(-(t - 2) / decay));
  }
  return v;
};

/** Narration loudness around a scene frame, averaged over +-4 frames so glows breathe instead of flicker. */
export const energy = (scene: Scene, frame: number) => {
  const m = scene.mouth;
  if (!m.length) return 0;
  let sum = 0;
  let weight = 0;
  for (let k = -4; k <= 4; k++) {
    const wgt = 5 - Math.abs(k);
    sum += (m[Math.min(m.length - 1, Math.max(0, frame + k))] ?? 0) * wgt;
    weight += wgt;
  }
  return sum / weight;
};

/** Seconds-scale idle sway so nothing on screen ever sits perfectly still. */
export const sway = (frame: number, period: number, amp: number, phase = 0) => amp * Math.sin((frame / period) * Math.PI * 2 + phase);

/** Embers that drift up through the background; they take the scene colour and get a kick at every cut. */
const Motes: React.FC<{tint: string; text: string; starts: number[]}> = ({tint, text, starts}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  let kick = 0;
  for (const f of starts.slice(1)) if (frame >= f) kick += 260 * (1 - Math.exp(-(frame - f) / 7));
  const span = height + 80;
  return (
    <>
      {Array.from({length: 30}, (_, k) => {
        const r = (key: string) => random(`mote-${key}-${k}`);
        const speed = 0.7 + r("v") * 1.6;
        const size = 2.5 + r("s") * 6.5;
        const y = ((((r("y") * span - frame * speed - kick * (0.5 + size / 9)) % span) + span) % span) - 40;
        const x = r("x") * width + sway(frame, 90 + r("p") * 120, 26 + r("a") * 30, r("ph") * 6.28);
        const twinkle = 0.55 + 0.45 * Math.sin(frame / (7 + r("t") * 9) + r("tp") * 6.28);
        const colored = k % 3 !== 0;
        return k % 7 === 0 ? (
          <circle key={k} cx={x} cy={y} r={size * 1.6} fill="none" stroke={tint} strokeWidth={2} strokeOpacity={0.3 * twinkle} />
        ) : (
          <circle key={k} cx={x} cy={y} r={size} fill={colored ? tint : text} fillOpacity={(colored ? 0.42 : 0.22) * twinkle} />
        );
      })}
    </>
  );
};

/** Glowing colour fields that drift and take on each scene's colour, over a moving dot grid. */
export const Background: React.FC<{p: Palette; tints: string[]; starts: number[]}> = ({p, tints, starts}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const i = sceneIndexAt(starts, frame);
  const fade = i === 0 ? 1 : spring({frame: frame - starts[i], fps, config: {damping: 30, stiffness: 50}});
  const field = (color: string, opacity: number) => (
    <AbsoluteFill
      style={{
        opacity,
        background: [
          `radial-gradient(48% 26% at ${50 + 22 * Math.sin(frame / 60)}% ${32 + 9 * Math.cos(frame / 45)}%, ${mix(color, 42)} 0%, transparent 72%)`,
          `radial-gradient(55% 30% at ${28 + 18 * Math.cos(frame / 75)}% ${74 + 7 * Math.sin(frame / 55)}%, ${mix(color, 22)} 0%, transparent 70%)`,
        ].join(","),
      }}
    />
  );
  const dy = -((frame * 0.9 + i * 22) % 44);
  return (
    <AbsoluteFill style={{background: `linear-gradient(180deg, ${p.bg2} 0%, ${p.bg} 55%, ${p.bg} 100%)`}}>
      {i > 0 ? field(tints[i - 1], 1 - fade) : null}
      {field(tints[i], fade)}
      <svg width={width} height={height} style={{position: "absolute", inset: 0}}>
        <defs>
          <pattern id="k-dots" width={44} height={44} patternUnits="userSpaceOnUse" patternTransform={`translate(0 ${dy})`}>
            <circle cx={22} cy={22} r={2.2} fill={p.text} fillOpacity={0.1} />
          </pattern>
        </defs>
        <rect width={width} height={height} fill="url(#k-dots)" />
        <Motes tint={tints[i]} text={p.text} starts={starts} />
      </svg>
      <AbsoluteFill style={{background: "radial-gradient(90% 60% at 50% 45%, transparent 55%, rgba(0,0,0,0.55) 100%)"}} />
    </AbsoluteFill>
  );
};

/** Brand row: Byte in a round avatar that glows while talking and hops at every cut, source and date, topic chip. */
export const Header: React.FC<{props: ShortProps; p: Palette; tint: string; mouth: number; sinceCut: number}> = ({
  props,
  p,
  tint,
  mouth,
  sinceCut,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame: frame - 1, fps, config: {damping: 16, stiffness: 140}});
  const live = 0.55 + 0.45 * Math.sin(frame / 5);
  const hopP = spring({frame: sinceCut, fps, config: {damping: 9, stiffness: 170, mass: 0.6}});
  const hop = -Math.sin(Math.min(1, hopP) * Math.PI) * 18;
  return (
    <div
      style={{
        position: "absolute",
        left: K.stage.x,
        top: K.header.y,
        width: K.stage.w,
        height: K.header.h,
        display: "flex",
        alignItems: "center",
        transform: `translateY(${(1 - enter) * -70}px)`,
        opacity: enter,
      }}
    >
      <div
        style={{
          width: 110,
          height: 110,
          flexShrink: 0,
          borderRadius: 55,
          background: p.bg2,
          border: `5px solid ${tint}`,
          boxShadow: `0 0 ${12 + 36 * mouth}px ${mix(tint, 35 + 45 * mouth)}`,
          overflow: "hidden",
          position: "relative",
          transform: `translateY(${hop}px) rotate(${hop * -0.4 + sway(frame, 110, 2.5)}deg) scale(${1 + 0.03 * mouth})`,
        }}
      >
        <div style={{position: "absolute", left: 3, top: 8, width: 94, height: 108}}>
          <Mascot theme={props.theme} mouth={mouth} talking={mouth > 0.08} drawP={1} />
        </div>
      </div>
      <div style={{marginLeft: 22, flex: 1, minWidth: 0}}>
        <div style={{fontFamily: DISPLAY, fontWeight: 800, fontSize: 58, lineHeight: 1, color: p.text, whiteSpace: "nowrap"}}>{props.brand.name}</div>
        <div
          style={{
            fontFamily: TEXT,
            fontWeight: 500,
            fontSize: 28,
            lineHeight: 1.2,
            marginTop: 6,
            color: p.dim,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {props.story.source} · {props.story.date}
        </div>
      </div>
      {props.story.topic ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            border: `3px solid ${tint}`,
            borderRadius: 999,
            padding: "8px 22px 6px 18px",
            fontFamily: DISPLAY,
            fontWeight: 700,
            fontSize: 34,
            letterSpacing: 1.5,
            textTransform: "uppercase",
            color: p.text,
            background: mix(tint, 14, p.bg),
            maxWidth: 330,
            whiteSpace: "nowrap",
            overflow: "hidden",
          }}
        >
          <span style={{width: 14, height: 14, borderRadius: 7, background: tint, opacity: live, flexShrink: 0}} />
          {props.story.topic}
        </div>
      ) : null}
    </div>
  );
};

/** Story-style progress: one segment per scene. */
export const Progress: React.FC<{scenes: Scene[]; starts: number[]; tint: string; p: Palette}> = ({scenes, starts, tint, p}) => {
  const frame = useCurrentFrame();
  const i = sceneIndexAt(starts, frame);
  return (
    <div style={{position: "absolute", left: K.stage.x, top: K.progress.y, width: K.stage.w, height: K.progress.h, display: "flex", gap: 10}}>
      {scenes.map((s, k) => {
        const fill = Math.min(1, Math.max(0, (frame - starts[k]) / s.durationInFrames));
        return (
          <div key={s.id} style={{flex: 1, borderRadius: 4, background: mix(p.text, 16), overflow: "hidden"}}>
            <div style={{width: `${fill * 100}%`, height: "100%", borderRadius: 4, background: k === i ? tint : mix(p.text, 85)}} />
          </div>
        );
      })}
    </div>
  );
};

const captionSize = (chars: number, longest: number) => {
  if (chars <= 10 && longest <= 9) return 128;
  if (chars <= 14 && longest <= 11) return 112;
  if (chars <= 18 && longest <= 13) return 98;
  return 84;
};

/** Karaoke captions: each word pops in as it is spoken; the current word sits on a colour slab. */
export const Captions: React.FC<{
  scenes: Scene[];
  starts: number[];
  p: Palette;
  tints: string[];
  maxWords: number;
  maxChars: number;
}> = ({scenes, starts, p, tints, maxWords, maxChars}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const i = sceneIndexAt(starts, frame);
  const scene = scenes[i];
  if (!scene) return null;
  const tint = tints[i];
  const tMs = ((frame - starts[i]) / fps) * 1000;
  const pages = paginate(scene.words, maxWords, maxChars);
  let pi = -1;
  for (let k = 0; k < pages.length; k++) {
    if (pages[k].startMs - LEAD_MS <= tMs) pi = k;
  }
  const page = pi >= 0 ? pages[pi] : null;
  if (!page) return null;
  const chars = page.words.reduce((n, w) => n + w.text.length + 1, -1);
  const longest = page.words.reduce((n, w) => Math.max(n, w.text.length), 0);
  const startFrame = (w: {startMs: number}) => starts[i] + Math.round(((w.startMs - LEAD_MS) / 1000) * fps);

  return (
    <div
      style={{
        position: "absolute",
        left: K.captions.x,
        top: K.captions.y,
        width: K.captions.w,
        height: K.captions.h,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          textAlign: "center",
          fontFamily: DISPLAY,
          fontWeight: 900,
          fontSize: captionSize(chars, longest),
          lineHeight: 1.08,
          textTransform: "uppercase",
          textWrap: "balance",
          letterSpacing: 0.5,
        }}
      >
        {page.words.map((w, k) => {
          const at = startFrame(w);
          const next = page.words[k + 1];
          const active = tMs >= w.startMs - LEAD_MS && (next ? tMs < next.startMs - LEAD_MS : tMs <= w.endMs + 300);
          const pop = spring({frame: frame - at, fps, config: {damping: 12, stiffness: 320, mass: 0.5}});
          const slab = spring({frame: frame - at, fps, config: {damping: 18, stiffness: 360, mass: 0.5}});
          return (
            <React.Fragment key={k}>
              {k > 0 ? " " : null}
              <span
                style={{
                  position: "relative",
                  display: "inline-block",
                  padding: "0 0.07em",
                  opacity: frame >= at ? 1 : 0,
                  transform: `translateY(${(1 - pop) * 26}px) scale(${0.72 + 0.28 * pop})`,
                  color: active ? p.ink : p.text,
                  textShadow: active ? "none" : `0 7px 0 ${p.ink}, 0 0 26px rgba(0,0,0,0.65)`,
                }}
              >
                {active ? (
                  <span
                    style={{
                      position: "absolute",
                      inset: "0.04em -0.02em -0.02em",
                      zIndex: -1,
                      background: tint,
                      borderRadius: "0.14em",
                      boxShadow: `0 8px 0 ${p.ink}`,
                      transform: `scaleX(${slab}) rotate(-2.5deg)`,
                      transformOrigin: "0 50%",
                    }}
                  />
                ) : null}
                {w.text}
              </span>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

/** A slanted colour panel sweeps across the stage at every scene change and hides the cut. */
export const Wipes: React.FC<{starts: number[]; tints: string[]; p: Palette}> = ({starts, tints, p}) => {
  const frame = useCurrentFrame();
  const box = {x: K.stage.x - 40, y: K.stage.y - 24, w: K.stage.w + 80, h: K.stage.h + 48};
  return (
    <div style={{position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, overflow: "hidden", pointerEvents: "none"}}>
      {starts.slice(1).map((f, k) => {
        const t = frame - f;
        if (t < -8 || t > 9) return null;
        const e = interpolate(t, [-8, 9], [0, 1], {easing: Easing.inOut(Easing.cubic)});
        const left = -1900 + e * 3100;
        const bar: React.CSSProperties = {position: "absolute", top: -120, height: box.h + 240, transform: "skewX(-12deg)"};
        // Every other cut sweeps the other way.
        return (
          <div key={f} style={{position: "absolute", inset: 0, transform: k % 2 ? "scaleX(-1)" : undefined}}>
            <div style={{...bar, left, width: 1700, background: tints[k + 1], borderRadius: 24}} />
            <div style={{...bar, left: left - 130, width: 54, background: p.text, opacity: 0.9, borderRadius: 12}} />
            <div style={{...bar, left: left - 230, width: 22, background: tints[k + 1], opacity: 0.7, borderRadius: 8}} />
          </div>
        );
      })}
    </div>
  );
};

/**
 * Words that rise out of a mask one after another. With `hits` (from spokenHits) each word jumps and
 * flashes `hitColor` when the narration says it.
 */
export const WordsRise: React.FC<{
  text: string;
  start: number;
  stagger?: number;
  style?: React.CSSProperties;
  color?: (word: string, k: number) => string | undefined;
  hits?: number[][];
  hitColor?: string;
  /** Idle float in px; words drift out of phase so the line ripples. */
  bob?: number;
}> = ({text, start, stagger = 3, style, color, hits, hitColor, bob = 0}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <div style={{textWrap: "balance", ...style}}>
      {words.map((w, k) => {
        const at = start + k * stagger;
        const s = spring({frame: frame - at, fps, config: {damping: 15, stiffness: 170, mass: 0.7}});
        // Hits before the word has finished rising would flash something not yet on screen.
        const h = hits ? pulse(frame, (hits[k] ?? []).filter((f) => f >= at + 8)) : 0;
        const base = color?.(w, k) ?? (style?.color as string | undefined) ?? "currentColor";
        const flash = hitColor && h > 0.01 ? mix(base === hitColor ? "#FFFFFF" : hitColor, Math.round(h * 100), base) : base;
        const float = bob ? sway(frame, 70, bob, k * 0.9) * Math.min(1, Math.max(0, (frame - at - 10) / 20)) : 0;
        return (
          <React.Fragment key={k}>
            {k > 0 ? " " : null}
            <span
              style={{
                display: "inline-block",
                overflow: frame - at > 14 ? "visible" : "hidden",
                padding: "0.08em 0.06em 0.14em",
                margin: "-0.08em -0.06em -0.14em",
                verticalAlign: "top",
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  transform: `translateY(${(1 - s) * 110}%) rotate(${(1 - s) * 7}deg)`,
                  transformOrigin: "0 100%",
                }}
              >
                <span
                  style={{
                    display: "inline-block",
                    transform: `translateY(calc(${float.toFixed(2)}px - ${(0.14 * h).toFixed(3)}em)) rotate(${(k % 2 ? 3 : -3) * h}deg) scale(${1 + 0.08 * h})`,
                    transformOrigin: "50% 90%",
                    color: flash,
                  }}
                >
                  {w}
                </span>
              </span>
            </span>
          </React.Fragment>
        );
      })}
    </div>
  );
};

const STRIP = Array.from({length: 40}, (_, q) => q % 10);

/**
 * Rolling-digit counter. Shows the value string exactly as written (so the number check still holds);
 * each digit spins twice past zero and settles, with vertical motion blur while it moves fast.
 */
export const Odometer: React.FC<{value: string; start: number; size: number; color: string; ink: string; id: string}> = ({
  value,
  start,
  size,
  color,
  ink,
  id,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const chars = [...value.trim()];
  const pos = (f: number, delay: number, digit: number) =>
    spring({frame: f - start - delay, fps, config: {damping: 17, stiffness: 85, mass: 1}}) * (20 + digit);
  let j = 0;
  return (
    <div
      style={{
        display: "flex",
        fontFamily: DISPLAY,
        fontWeight: 900,
        fontSize: size,
        lineHeight: 1,
        color,
        fontVariantNumeric: "tabular-nums",
        whiteSpace: "nowrap",
        filter: `drop-shadow(0 10px 0 ${ink}) drop-shadow(0 0 34px ${mix(color, 55)})`,
      }}
    >
      {chars.map((c, k) => {
        if (!/\d/.test(c)) {
          const s = spring({frame: frame - start - 2 - k, fps, config: {damping: 12, stiffness: 200}});
          return (
            <span key={k} style={{display: "inline-block", height: "1em", whiteSpace: "pre", transform: `scale(${s})`, opacity: Math.min(1, s * 1.5)}}>
              {c}
            </span>
          );
        }
        const delay = j++ * 2;
        const digit = Number(c);
        const y = pos(frame, delay, digit);
        const speed = Math.abs(y - pos(frame - 1, delay, digit));
        const blur = Math.min(16, speed * size * 0.045);
        const fid = `${id}-vb-${k}`;
        return (
          <span key={k} style={{display: "inline-block", height: "1em", overflow: "hidden", position: "relative", filter: blur > 0.3 ? `url(#${fid})` : undefined}}>
            <svg width={0} height={0} style={{position: "absolute"}}>
              <filter id={fid} x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation={`0 ${blur.toFixed(2)}`} />
              </filter>
            </svg>
            <span style={{display: "block", transform: `translateY(${-y}em)`}}>
              {STRIP.map((n, q) => (
                <span key={q} style={{display: "block", height: "1em"}}>
                  {n}
                </span>
              ))}
            </span>
          </span>
        );
      })}
    </div>
  );
};

/** Expanding ring at an impact frame. */
export const Shockwave: React.FC<{at: number; cx: number; cy: number; color: string; maxR?: number}> = ({at, cx, cy, color, maxR = 380}) => {
  const frame = useCurrentFrame();
  const t = frame - at;
  if (t < 0 || t > 18) return null;
  const e = Easing.out(Easing.cubic)(t / 18);
  return <circle cx={cx} cy={cy} r={40 + (maxR - 40) * e} fill="none" stroke={color} strokeWidth={16 * (1 - e) + 1} opacity={1 - e} />;
};
