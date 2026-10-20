import React, {useMemo} from "react";
import {AbsoluteFill, Html5Audio, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {paginate, sceneIndexAt} from "../../components/Captions";
import {DrawnIcon} from "../../components/Draw";
import {DISPLAY, TEXT, ensureFonts} from "../../fonts";
import {iconNode} from "../../icons";
import {sceneStarts} from "../../NewsShort";
import {fitSize, headlineSize} from "../../scenes/common";
import {SAFE, defaultTheme} from "../../theme";
import type {Scene, ShortProps, Theme} from "../../types";

ensureFonts();

// Baseline for comparison: what a plain slideshow tool (FFmpeg / MoviePy style) gives you.
// One static card per scene, slow zoom, dip-to-black between scenes, plain subtitles.

const big = (size: number, color: string): React.CSSProperties => ({
  fontFamily: DISPLAY,
  fontWeight: 800,
  fontSize: size,
  lineHeight: 1.0,
  color,
  textAlign: "center",
  textWrap: "balance",
});

const small: React.CSSProperties = {fontFamily: TEXT, fontWeight: 600, fontSize: 54, lineHeight: 1.2, color: "#C9CED8", textAlign: "center", textWrap: "balance"};

const Card: React.FC<{scene: Scene; brand: string; theme: Theme}> = ({scene, brand, theme}) => {
  const v = scene.visual;
  switch (v.type) {
    case "headline":
      return (
        <>
          {v.tag ? <div style={{...small, color: theme.accent, textTransform: "uppercase", marginBottom: 30}}>{v.tag}</div> : null}
          <div style={big(headlineSize(v.text), "#FFFFFF")}>{v.text}</div>
        </>
      );
    case "stat":
      return (
        <>
          <div style={big(fitSize(v.value, [[3, 300], [5, 260], [7, 210]], 160), theme.accent)}>{v.value}</div>
          <div style={{...small, marginTop: 30}}>{v.label}</div>
        </>
      );
    case "icon":
      return (
        <>
          <DrawnIcon node={iconNode(v.icon)} p={1} size={220} color="#FFFFFF" strokeWidth={1.6} />
          <div style={{...big(fitSize(v.text, [[18, 92], [30, 80]], 66), "#FFFFFF"), marginTop: 40}}>{v.text}</div>
        </>
      );
    case "versus":
      return (
        <>
          <div style={big(96, "#FFFFFF")}>{v.left}</div>
          <div style={{...small, color: theme.accent, margin: "20px 0"}}>vs</div>
          <div style={big(96, "#FFFFFF")}>{v.right}</div>
          {v.label ? <div style={{...small, marginTop: 40}}>{v.label}</div> : null}
        </>
      );
    case "bullets":
      return (
        <div style={{display: "flex", flexDirection: "column", gap: 34}}>
          {v.items.slice(0, 4).map((it, k) => (
            <div key={k} style={{...big(fitSize(it, [[14, 84], [24, 72]], 60), "#FFFFFF"), textAlign: "left"}}>
              • {it}
            </div>
          ))}
        </div>
      );
    case "outro":
      return (
        <>
          <div style={big(150, "#FFFFFF")}>{brand}</div>
          <div style={{...small, color: theme.accent, marginTop: 30}}>{v.text}</div>
        </>
      );
    default:
      return null;
  }
};

const Slide: React.FC<{scene: Scene; brand: string; theme: Theme}> = ({scene, brand, theme}) => {
  const frame = useCurrentFrame();
  const d = scene.durationInFrames;
  const fade = Math.min(
    interpolate(frame, [0, 8], [0, 1], {extrapolateRight: "clamp"}),
    interpolate(frame, [d - 8, d], [1, 0], {extrapolateLeft: "clamp"}),
  );
  const zoom = interpolate(frame, [0, d], [1, 1.06]);
  return (
    <AbsoluteFill
      style={{
        opacity: fade,
        transform: `scale(${zoom})`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: `${SAFE.top + 60}px 110px 860px`,
      }}
    >
      <Card scene={scene} brand={brand} theme={theme} />
    </AbsoluteFill>
  );
};

/** Plain subtitles: the current few words, no highlighting or motion. */
const Subtitles: React.FC<{scenes: Scene[]; starts: number[]; maxWords: number; maxChars: number}> = ({scenes, starts, maxWords, maxChars}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const i = sceneIndexAt(starts, frame);
  const scene = scenes[i];
  if (!scene) return null;
  const tMs = ((frame - starts[i]) / fps) * 1000;
  const page = paginate(scene.words, maxWords * 2, maxChars * 2).find((pg) => tMs >= pg.startMs - 70 && tMs <= pg.endMs + 250);
  if (!page) return null;
  return (
    <div style={{position: "absolute", left: SAFE.left, width: SAFE.rightRail - SAFE.left, top: 1230, textAlign: "center"}}>
      <span
        style={{
          fontFamily: TEXT,
          fontWeight: 600,
          fontSize: 62,
          lineHeight: 1.2,
          color: "#FFFFFF",
          textShadow: "0 0 6px #000, 0 0 6px #000, 0 3px 4px #000",
        }}
      >
        {page.words.map((w) => w.text).join(" ")}
      </span>
    </div>
  );
};

export const SlideshowShort: React.FC<ShortProps> = (input) => {
  const theme = {...defaultTheme, ...input.theme};
  const {scenes} = input;
  const starts = useMemo(() => sceneStarts(scenes), [scenes]);
  return (
    <AbsoluteFill style={{backgroundColor: "#14171D"}}>
      {scenes.map((s, k) => (
        <Sequence key={s.id} from={starts[k]} durationInFrames={s.durationInFrames} name={`${k + 1}. ${s.visual.type}`}>
          <Slide scene={s} brand={input.brand.name} theme={theme} />
          {s.audio ? <Html5Audio src={staticFile(s.audio)} /> : null}
        </Sequence>
      ))}
      {input.captions.enabled ? <Subtitles scenes={scenes} starts={starts} maxWords={input.captions.maxWords} maxChars={input.captions.maxChars} /> : null}
      {input.music ? <Html5Audio src={staticFile(input.music.src)} volume={input.music.volume} loop /> : null}
    </AbsoluteFill>
  );
};
