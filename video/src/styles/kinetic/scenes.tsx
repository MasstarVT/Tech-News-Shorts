import {Bell} from "lucide";
import React from "react";
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {Drawn, DrawnIcon, type IconNode, prog} from "../../components/Draw";
import {Mascot} from "../../components/Mascot";
import {DISPLAY, TEXT} from "../../fonts";
import {iconNode} from "../../icons";
import {mouthAt} from "../../NewsShort";
import {fitSize, headlineSize} from "../../scenes/common";
import type {Scene, Theme, Trend} from "../../types";
import {K, type Palette, Odometer, Shockwave, WordsRise, energy, mix, pulse, shake, spokenHits, sway} from "./parts";

const W = K.stage.w;
const H = K.stage.h;

type Common = {p: Palette; tint: string; d: number; scene: Scene};

/** Frame the stat number lands on (the odometer settles one digit after another). */
const statLand = (value: string) => 4 + Math.max(0, (value.match(/\d/g) ?? []).length - 1) * 2 + 16;

/** When an element first gets its hits: hits before this would land during its entrance. */
const ENTERED = 20;

/**
 * Camera punch-in frames: the first time each on-screen word is said, at least 22 frames apart,
 * clear of the entrance shake and of the exit blur. At most three per scene.
 */
const sceneBeats = (scene: Scene, fps: number) => {
  const v = scene.visual;
  const d = scene.durationInFrames;
  const on = (text: string, from = ENTERED) => spokenHits(text, scene.words, fps).map((h) => h.find((f) => f >= from));
  const firsts =
    v.type === "headline" || v.type === "icon"
      ? on(v.text, 24)
      : v.type === "stat"
        ? on(`${v.value} ${v.label}`, statLand(v.value) + 10)
        : v.type === "versus"
          ? on(`${v.left} ${v.right}`, 26)
          : v.type === "bullets"
            ? on(v.items.join(" "))
            : [];
  const out: number[] = [];
  for (const f of firsts.filter((f): f is number => f !== undefined).sort((a, b) => a - b)) {
    if (f <= d - 14 && (!out.length || f - out[out.length - 1] >= 22)) out.push(f);
  }
  return out.slice(0, 3);
};

/** Push-in plus keyword punches, at their peak. Anything that runs to the right rail sizes itself with this. */
const MAX_ZOOM = 1.07;

/**
 * Positions a scene on the stage: a handheld drift and slow push-in while it plays, a quick punch-in
 * whenever the voice says a word that is on screen, zoom-through blur on the way out.
 */
export const Stage: React.FC<{scene: Scene; children: React.ReactNode}> = ({scene, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const d = scene.durationInFrames;
  const push = interpolate(frame, [0, d], [1, 1.035], {extrapolateRight: "clamp"});
  const out = interpolate(frame, [d - 6, d], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic)});
  let punch = 0;
  let kick = 0;
  sceneBeats(scene, fps).forEach((f, k) => {
    const v = pulse(frame, [f], 7);
    punch = Math.max(punch, v);
    kick += (k % 2 ? 1 : -1) * v;
  });
  const x = sway(frame, 150, 7, 1);
  const y = sway(frame, 110, 6);
  const rot = sway(frame, 190, 0.5, 2) + kick * 0.7;
  return (
    <div
      style={{
        position: "absolute",
        left: K.stage.x,
        top: K.stage.y,
        width: W,
        height: H,
        transform: `translate(${x}px, ${y}px) rotate(${rot}deg) scale(${push + (MAX_ZOOM - 1.035) * punch + 0.12 * out})`,
        opacity: 1 - out,
        filter: out > 0.01 ? `blur(${out * 10}px)` : undefined,
      }}
    >
      {children}
    </div>
  );
};

/** Ignore hits that land while an element is still entering. */
const after = (hits: number[][], from: number) => [...new Set(hits.flat().filter((f) => f >= from))];

/** The word to colour in a headline: one with a number, else the longest real word. */
const keyWord = (text: string) => {
  const words = text.split(/\s+/).filter(Boolean);
  const digit = words.findIndex((w) => /\d/.test(w));
  if (digit >= 0) return digit;
  let best = -1;
  let len = 4;
  words.forEach((w, k) => {
    const n = w.replace(/[^\p{L}\p{N}]/gu, "").length;
    if (n > len) {
      best = k;
      len = n;
    }
  });
  return best;
};

const Headline: React.FC<Common & {text: string; tag?: string}> = ({text, tag, p, tint, scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const n = text.split(/\s+/).filter(Boolean).length;
  const hl = keyWord(text);
  const chip = spring({frame: frame - 14, fps, config: {damping: 11, stiffness: 200, mass: 0.7}});
  const drawn = 6 + n * 3;
  const swoosh = prog(frame, drawn, 12, Easing.out(Easing.cubic));
  const sh = shake(frame, tag ? [18] : [], 12);
  // A glint runs along the underline every couple of seconds once it is drawn.
  const glint = frame >= drawn + 16 ? ((frame - drawn - 16) % 54) / 18 : 2;
  const e = energy(scene, frame);
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "0 16px",
        transform: `translate(${sh.x}px, ${sh.y + sway(frame, 80, 8)}px) rotate(${sway(frame, 140, 0.7, 1)}deg)`,
      }}
    >
      {tag ? (
        <div
          style={{
            alignSelf: "flex-start",
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginBottom: 36,
            padding: "8px 26px 6px 22px",
            borderRadius: 14,
            background: p.hot,
            color: "#fff",
            fontFamily: DISPLAY,
            fontWeight: 800,
            fontSize: 54,
            letterSpacing: 3,
            textTransform: "uppercase",
            boxShadow: `0 10px 0 ${p.ink}, 0 0 ${10 + 40 * e}px ${mix(p.hot, 30 + 40 * e)}`,
            transform: `scale(${2.2 - 1.2 * chip}) rotate(${-3 - (1 - chip) * 10 + sway(frame, 46, 1.8) * chip}deg)`,
            transformOrigin: "0 50%",
            opacity: Math.min(1, chip * 1.8),
          }}
        >
          <span style={{width: 20, height: 20, borderRadius: 10, background: "#fff", opacity: 0.5 + 0.5 * Math.sin(frame / 4)}} />
          {tag}
        </div>
      ) : null}
      <WordsRise
        text={text}
        start={3}
        stagger={3}
        color={(_, k) => (k === hl ? tint : undefined)}
        hits={spokenHits(text, scene.words, fps)}
        hitColor={tint}
        bob={5}
        style={{
          fontFamily: DISPLAY,
          fontWeight: 900,
          fontSize: headlineSize(text) * 1.04,
          lineHeight: 0.98,
          color: p.text,
          textShadow: `0 8px 0 ${p.ink}`,
        }}
      />
      <svg width={300} height={40} style={{marginTop: 22, overflow: "visible"}}>
        <Drawn tag="path" p={swoosh} attrs={{d: "M 6 24 Q 120 6 290 16", stroke: tint, strokeWidth: 14, strokeLinecap: "round"}} />
        {glint < 1 ? (
          <path
            d="M 6 24 Q 120 6 290 16"
            pathLength={100}
            fill="none"
            stroke="#FFFFFF"
            strokeOpacity={0.85}
            strokeWidth={8}
            strokeLinecap="round"
            strokeDasharray="12 200"
            strokeDashoffset={12 - glint * 112}
          />
        ) : null}
      </svg>
    </div>
  );
};

const wedge = (k: number, n: number, r: number) => {
  const a0 = (k / n) * Math.PI * 2;
  const a1 = a0 + Math.PI / n;
  return `M 0 0 L ${r * Math.cos(a0)} ${r * Math.sin(a0)} A ${r} ${r} 0 0 1 ${r * Math.cos(a1)} ${r * Math.sin(a1)} Z`;
};

const Stat: React.FC<Common & {value: string; label: string; trend: Trend; id: string}> = ({value, label, trend, p, tint, id, scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const size = fitSize(value, [[3, 320], [5, 270], [7, 215], [9, 175]], 140);
  const land = statLand(value);
  const sh = shake(frame, [land], 16);
  const rays = spring({frame: frame - 2, fps, config: {damping: 20, stiffness: 90}});
  const color = trend === "down" ? p.hot : tint;
  const cx = W / 2;
  const cy = trend === "none" ? 290 : 330;
  const R = 470;
  const e = energy(scene, frame);
  // Saying the number again thumps it and sends out another ring.
  const said = after(spokenHits(value, scene.words, fps), land + 8);
  const thump = pulse(frame, said, 9);
  return (
    <div style={{position: "absolute", inset: 0, transform: `translate(${sh.x}px, ${sh.y}px)`}}>
      <svg width={W} height={H} style={{position: "absolute", inset: 0, overflow: "visible"}}>
        <defs>
          <radialGradient id={`${id}-ray`} cx={0} cy={0} r={R} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor={color} stopOpacity={0.5} />
            <stop offset="1" stopColor={color} stopOpacity={0} />
          </radialGradient>
        </defs>
        <g transform={`translate(${cx} ${cy}) rotate(${frame * 0.6}) scale(${rays * (1 + 0.1 * e + 0.12 * thump)})`} opacity={0.75 + 0.25 * e}>
          {Array.from({length: 14}, (_, k) => (
            <path key={k} d={wedge(k, 14, R)} fill={`url(#${id}-ray)`} />
          ))}
        </g>
        {[land, ...said].map((f) => (
          <Shockwave key={f} at={f} cx={cx} cy={cy} color={color} maxR={400} />
        ))}
      </svg>
      <div style={{position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"}}>
        {trend !== "none" ? (
          <div style={{height: 130, marginBottom: 4, transform: `translateY(${(trend === "down" ? 1 : -1) * Math.abs(Math.sin(frame / 10)) * 10}px)`}}>
            <DrawnIcon node={iconNode(trend === "down" ? "chart-down" : "chart-up")} p={prog(frame, 6, 18)} size={130} color={color} strokeWidth={2.4} />
          </div>
        ) : null}
        <div style={{transform: `scale(${1 + 0.025 * e + 0.09 * thump}) rotate(${sway(frame, 90, 1.2) * Math.min(1, frame / 40)}deg)`}}>
          <Odometer value={value} start={4} size={size} color={color} ink={p.ink} id={id} />
        </div>
        <WordsRise
          text={label}
          start={land - 6}
          stagger={2}
          hits={spokenHits(label, scene.words, fps)}
          hitColor={color}
          style={{fontFamily: TEXT, fontWeight: 600, fontSize: 58, lineHeight: 1.15, color: p.text, textAlign: "center", maxWidth: 760, marginTop: 30}}
        />
      </div>
    </div>
  );
};

const IconCallout: React.FC<Common & {icon: string; text: string; id: string}> = ({icon, text, p, tint, id, scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({frame: frame - 1, fps, config: {damping: 12, stiffness: 150, mass: 0.8}});
  const float = Math.sin(frame / 22) * 8;
  const cx = W / 2;
  const cy = 250 + float;
  const R = 150;
  const size = fitSize(text, [[18, 96], [30, 84], [46, 72]], 62);
  const pulseT = frame < 12 ? -1 : (frame - 12) % 42;
  const e = energy(scene, frame);
  const hits = spokenHits(text, scene.words, fps);
  const said = pulse(frame, after(hits, ENTERED + 8), 8);
  // The icon gives a little shake every couple of seconds, like it wants attention.
  const jt = frame < 30 ? -1 : (frame - 30) % 66;
  const jiggle = jt < 0 ? 0 : Math.sin(jt / 1.6) * 11 * Math.exp(-jt / 8);
  const badge = pop * (1 + 0.04 * e + 0.07 * said);
  return (
    <div style={{position: "absolute", inset: 0}}>
      <svg width={W} height={H} style={{position: "absolute", inset: 0, overflow: "visible"}}>
        <defs>
          <radialGradient id={`${id}-glow`}>
            <stop offset="0" stopColor={tint} stopOpacity={0.5} />
            <stop offset="1" stopColor={tint} stopOpacity={0} />
          </radialGradient>
        </defs>
        <circle cx={cx} cy={cy} r={R * 2 * pop * (1 + 0.18 * e + 0.15 * said)} fill={`url(#${id}-glow)`} />
        {pulseT >= 0 ? (
          <circle cx={cx} cy={cy} r={R + pulseT * 4.5} fill="none" stroke={tint} strokeWidth={4} opacity={0.6 * (1 - pulseT / 42)} />
        ) : null}
        {[0, 1].map((o) => {
          const rx = R + 70 + o * 42;
          const ry = rx * 0.34;
          const a = frame * (o ? 0.075 : -0.055) + o * 2;
          return (
            <g key={o} transform={`translate(${cx} ${cy}) rotate(${o ? -24 : 18}) scale(${pop})`}>
              <ellipse rx={rx} ry={ry} fill="none" stroke={tint} strokeOpacity={0.55} strokeWidth={3} strokeDasharray="10 14" strokeDashoffset={-frame * 1.5} />
              <circle cx={rx * Math.cos(a)} cy={ry * Math.sin(a)} r={o ? 9 : 12} fill={o ? p.text : tint} />
            </g>
          );
        })}
      </svg>
      <div
        style={{
          position: "absolute",
          left: cx - R,
          top: cy - R,
          width: R * 2,
          height: R * 2,
          borderRadius: R,
          background: p.bg2,
          border: `6px solid ${tint}`,
          boxShadow: `0 14px 0 ${p.ink}, inset 0 0 ${40 + 30 * e}px ${mix(tint, 30 + 30 * e)}`,
          transform: `scale(${badge})`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div style={{display: "flex", transform: `rotate(${jiggle}deg) scale(${1 + 0.08 * said})`}}>
          <DrawnIcon node={iconNode(icon)} p={prog(frame, 6, 22, Easing.inOut(Easing.quad))} size={180} color={p.text} strokeWidth={1.7} />
        </div>
      </div>
      <WordsRise
        text={text}
        start={14}
        stagger={3}
        hits={hits}
        hitColor={tint}
        bob={4}
        style={{
          position: "absolute",
          left: 90,
          top: 250 + R + 92,
          width: 760,
          textAlign: "center",
          fontFamily: DISPLAY,
          fontWeight: 800,
          fontSize: size,
          lineHeight: 1.0,
          color: p.text,
          textShadow: `0 6px 0 ${p.ink}`,
        }}
      />
    </div>
  );
};

const Versus: React.FC<Common & {left: string; right: string; label?: string}> = ({left, right, label, p, scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const e = energy(scene, frame);
  const leftHits = spokenHits(left, scene.words, fps);
  const rightHits = spokenHits(right, scene.words, fps);
  const settle = Math.min(1, Math.max(0, (frame - 18) / 20));
  const cardW = 410;
  const cardH = 330;
  const top = 90;
  const ls = spring({frame: frame - 1, fps, config: {damping: 13, stiffness: 170, mass: 0.9}});
  const rs = spring({frame: frame - 5, fps, config: {damping: 13, stiffness: 170, mass: 0.9}});
  const vs = spring({frame: frame - 13, fps, config: {damping: 9, stiffness: 220, mass: 0.6}});
  const sh = shake(frame, [16], 18);
  const longest = left.length > right.length ? left : right;
  const size = fitSize(longest, [[7, 100], [12, 82], [20, 66]], 54);
  const cy = top + cardH / 2;
  const burstT = frame - 16;

  // Each card bobs out of step with the other and jumps forward when the voice names it.
  const card = (x: number, text: string, color: string, s: number, dir: number, hits: number[][], start: number) => {
    const named = pulse(frame, after(hits, ENTERED + 6), 9);
    const bob = sway(frame, 56, 9, dir > 0 ? Math.PI : 0) * settle;
    const tilt = dir * (2 + (1 - s) * 14) + sway(frame, 84, 1.4, dir > 0 ? 1 : 0) * settle - dir * 2.5 * named;
    return (
    <div
      style={{
        position: "absolute",
        left: x,
        top,
        width: cardW,
        height: cardH,
        borderRadius: 30,
        border: `6px solid ${color}`,
        background: mix(color, 22 + 18 * named, p.bg2),
        boxShadow: `0 16px 0 ${p.ink}, 0 0 ${60 * named}px ${mix(color, 70 * named)}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: 28,
        boxSizing: "border-box",
        fontFamily: DISPLAY,
        fontWeight: 800,
        fontSize: size,
        lineHeight: 0.98,
        color: p.text,
        textWrap: "balance",
        transform: `translateX(${(1 - s) * dir * 820}px) translateY(${bob}px) rotate(${tilt}deg) scale(${1 + 0.06 * named})`,
      }}
    >
      <WordsRise text={text} start={start} stagger={2} hits={hits} hitColor={p.accent} />
    </div>
    );
  };

  return (
    <div style={{position: "absolute", inset: 0, transform: `translate(${sh.x}px, ${sh.y}px)`}}>
      {card(18, left, p.cool, ls, -1, leftHits, 4)}
      {card(W - 18 - cardW, right, p.hot, rs, 1, rightHits, 8)}
      <svg width={W} height={H} style={{position: "absolute", inset: 0, overflow: "visible"}}>
        {burstT >= 0 && burstT <= 14
          ? Array.from({length: 10}, (_, k) => {
              const a = (k / 10) * Math.PI * 2 + 0.3;
              const r0 = 90 + burstT * 9;
              const r1 = r0 + 46 * (1 - burstT / 14);
              return (
                <line
                  key={k}
                  x1={W / 2 + Math.cos(a) * r0}
                  y1={cy + Math.sin(a) * r0}
                  x2={W / 2 + Math.cos(a) * r1}
                  y2={cy + Math.sin(a) * r1}
                  stroke={p.accent}
                  strokeWidth={8}
                  strokeLinecap="round"
                  opacity={1 - burstT / 14}
                />
              );
            })
          : null}
      </svg>
      <div
        style={{
          position: "absolute",
          left: W / 2 - 78,
          top: cy - 78,
          width: 156,
          height: 156,
          borderRadius: 78,
          background: p.accent,
          border: `8px solid ${p.ink}`,
          boxSizing: "border-box",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: DISPLAY,
          fontWeight: 900,
          fontSize: 76,
          color: p.ink,
          transform: `scale(${vs * (1 + 0.07 * e)}) rotate(${(1 - vs) * -200 + sway(frame, 60, 8) * settle}deg)`,
        }}
      >
        VS
      </div>
      {label ? (
        <WordsRise
          text={label}
          start={22}
          stagger={2}
          hits={spokenHits(label, scene.words, fps)}
          hitColor={p.accent}
          style={{
            position: "absolute",
            left: 90,
            top: top + cardH + 80,
            width: 760,
            textAlign: "center",
            fontFamily: TEXT,
            fontWeight: 600,
            fontSize: 56,
            lineHeight: 1.15,
            color: p.dim,
          }}
        />
      ) : null}
    </div>
  );
};

/**
 * When each bullet comes in: as soon as the voice reaches one of its words (numbers or words of four
 * letters or more, said after the previous bullet came in), else evenly over the scene. The first is always early.
 */
const bulletStarts = (list: string[], scene: Scene, fps: number) => {
  const d = scene.durationInFrames;
  const span = (d * 0.75) / Math.max(1, list.length);
  const out: number[] = [];
  list.forEach((item, k) => {
    if (k === 0) {
      out.push(3);
      return;
    }
    const prev = out[k - 1];
    const words = item.split(/\s+/).filter(Boolean);
    const said = spokenHits(item, scene.words, fps)
      .filter((_, j) => /\d/.test(words[j]) || words[j].replace(/[^\p{L}\p{N}]/gu, "").length >= 4)
      .flat()
      .filter((f) => f >= prev + 10 && f < d - 20);
    out.push(said.length ? Math.max(prev + 10, Math.min(...said) - 4) : Math.max(prev + 10, 3 + k * span));
  });
  return out;
};

const Bullets: React.FC<Common & {items: string[]}> = ({items, p, tint, d, scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const list = items.slice(0, 4);
  const n = Math.max(1, list.length);
  const gap = 24;
  const rowH = Math.min(n <= 2 ? 220 : 170, (H - 20 - gap * (n - 1)) / n);
  const top = (H - (rowH * n + gap * (n - 1))) / 2;
  const starts = bulletStarts(list, scene, fps);
  const startOf = (k: number) => starts[k] ?? d;
  const current = list.reduce((c, _, k) => (frame >= startOf(k) ? k : c), 0);
  const longest = list.reduce((a, b) => (b.length > a.length ? b : a), "");
  const size = fitSize(longest, [[14, 80], [22, 70], [32, 62]], 54);
  // Keeps the rows left of the like/comment rail even at the stage's peak zoom (scaled about the stage centre).
  const W_CARD = Math.floor(W / 2 + (K.captions.w - W / 2 - 8) / MAX_ZOOM);
  const e = energy(scene, frame);

  return (
    <div style={{position: "absolute", inset: 0}}>
      {list.map((item, k) => {
        const s = spring({frame: frame - startOf(k), fps, config: {damping: 14, stiffness: 170, mass: 0.8}});
        const done = k < current;
        const active = k === current;
        const tick = prog(frame, startOf(k + 1), 8);
        const tickPop = spring({frame: frame - startOf(k + 1), fps, config: {damping: 8, stiffness: 220, mass: 0.5}});
        const end = k + 1 < list.length ? startOf(k + 1) : d - 6;
        const fill = Math.min(1, Math.max(0, (frame - startOf(k)) / Math.max(1, end - startOf(k))));
        return (
          <div
            key={k}
            style={{
              position: "absolute",
              left: 0,
              top: top + k * (rowH + gap),
              width: W_CARD,
              height: rowH,
              display: "flex",
              alignItems: "center",
              padding: "0 30px",
              boxSizing: "border-box",
              borderRadius: 24,
              borderLeft: `12px solid ${active ? tint : mix(p.text, 30)}`,
              background: active ? mix(tint, 16, p.bg2) : p.bg2,
              boxShadow: active ? `0 12px 0 ${p.ink}, 0 0 ${16 + 34 * e}px ${mix(tint, 22 + 30 * e)}` : `0 12px 0 ${p.ink}`,
              transform: `translateX(${(1 - s) * 1200}px) translateY(${active ? sway(frame, 60, 4) : 0}px) scale(${active ? 1 : 0.965})`,
              visibility: s < 0.005 ? "hidden" : "visible",
              transformOrigin: "0 50%",
              opacity: done ? 0.62 : 1,
              overflow: "hidden",
            }}
          >
            <svg width={84} height={84} viewBox="0 0 84 84" style={{flexShrink: 0, overflow: "visible"}}>
              {active ? (
                <circle cx={42} cy={42} r={42} fill="none" stroke={tint} strokeOpacity={0.6} strokeWidth={3} strokeDasharray="8 10" transform={`rotate(${frame * 3} 42 42)`} />
              ) : null}
              <g transform={done ? `translate(42 42) scale(${0.6 + 0.4 * tickPop}) translate(-42 -42)` : undefined}>
                <circle cx={42} cy={42} r={36} fill={done ? tint : "none"} stroke={tint} strokeWidth={5} />
                {done ? (
                  <Drawn tag="polyline" p={tick} attrs={{points: "25,43 37,55 60,30", stroke: p.ink, strokeWidth: 9, strokeLinecap: "round", strokeLinejoin: "round"}} />
                ) : (
                  <text x={42} y={55} textAnchor="middle" fontFamily={DISPLAY} fontWeight={800} fontSize={38} fill={tint}>
                    {String(k + 1).padStart(2, "0")}
                  </text>
                )}
              </g>
            </svg>
            <WordsRise
              text={item}
              start={startOf(k) + 4}
              stagger={2}
              hits={spokenHits(item, scene.words, fps)}
              hitColor={tint}
              style={{marginLeft: 28, fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 1.0, color: p.text}}
            />
            {active ? <div style={{position: "absolute", left: 0, bottom: 0, height: 7, width: `${fill * 100}%`, background: tint, opacity: 0.85}} /> : null}
          </div>
        );
      })}
    </div>
  );
};

const Outro: React.FC<Common & {text: string; brand: string; theme: Theme}> = ({text, brand, scene, theme, p, tint}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const mouth = mouthAt(scene, frame);
  const rise = spring({frame: frame - 6, fps, config: {damping: 12, stiffness: 120, mass: 0.9}});
  const brandSize = fitSize(brand, [[8, 190], [12, 150], [18, 116]], 92);
  const size = fitSize(text, [[22, 64], [36, 56]], 48);
  const bell = spring({frame: frame - 24, fps, config: {damping: 8, stiffness: 160, mass: 0.6}});
  const ring = frame > 30 ? Math.sin((frame - 30) / 2.2) * 14 * Math.exp(-((frame - 30) % 60) / 14) : 0;
  return (
    <div style={{position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"}}>
      <div
        style={{
          position: "relative",
          width: 230,
          height: 265,
          transform: `translateY(${(1 - rise) * 260}px) rotate(${sway(frame, 64, 3)}deg) scale(${1 + 0.04 * energy(scene, frame)})`,
          opacity: Math.min(1, rise * 2),
        }}
      >
        <div style={{position: "absolute", inset: -60, borderRadius: "50%", background: `radial-gradient(closest-side, ${mix(tint, 45)}, transparent)`}} />
        <Mascot theme={theme} mouth={mouth} talking={mouth > 0.08} drawP={1} />
      </div>
      <div style={{display: "flex", marginTop: 20, fontFamily: DISPLAY, fontWeight: 900, fontSize: brandSize, lineHeight: 0.92, color: p.text, whiteSpace: "pre"}}>
        {[...brand].map((c, k) => {
          const s = spring({frame: frame - 2 - k * 2, fps, config: {damping: 10, stiffness: 180, mass: 0.6}});
          // Once landed, the letters ripple like a stadium wave.
          const wave = sway(frame, 48, 9, -k * 0.7) * Math.min(1, Math.max(0, (frame - 22 - k * 2) / 16));
          return (
            <span
              key={k}
              style={{
                display: "inline-block",
                transform: `translateY(${(1 - s) * -170 + wave}px) rotate(${(1 - s) * (k % 2 ? 22 : -22)}deg)`,
                opacity: Math.min(1, s * 2),
                textShadow: `0 9px 0 ${p.ink}`,
              }}
            >
              {c}
            </span>
          );
        })}
      </div>
      <div style={{display: "flex", alignItems: "center", gap: 18, marginTop: 30, maxWidth: 820}}>
        <div style={{transform: `scale(${bell}) rotate(${ring}deg)`, transformOrigin: "50% 10%", flexShrink: 0}}>
          <DrawnIcon node={Bell as unknown as IconNode} p={1} size={64} color={tint} strokeWidth={2.4} />
        </div>
        <WordsRise text={text} start={16} stagger={2} style={{fontFamily: TEXT, fontWeight: 700, fontSize: size, lineHeight: 1.12, color: tint}} />
      </div>
    </div>
  );
};

export const SceneVisual: React.FC<{scene: Scene; p: Palette; tint: string; brand: string; theme: Theme}> = ({scene, p, tint, brand, theme}) => {
  const v = scene.visual;
  const c: Common = {p, tint, d: scene.durationInFrames, scene};
  const id = `k-${scene.id}`;
  switch (v.type) {
    case "headline":
      return <Headline {...c} text={v.text} tag={v.tag} />;
    case "stat":
      return <Stat {...c} value={v.value} label={v.label} trend={v.trend ?? "none"} id={id} />;
    case "icon":
      return <IconCallout {...c} icon={v.icon} text={v.text} id={id} />;
    case "versus":
      return <Versus {...c} left={v.left} right={v.right} label={v.label} />;
    case "bullets":
      return <Bullets {...c} items={v.items} />;
    case "outro":
      return <Outro {...c} text={v.text} brand={brand} theme={theme} />;
    default:
      return null;
  }
};
