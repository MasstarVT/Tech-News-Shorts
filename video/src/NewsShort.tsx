import React, {useMemo} from "react";
import {AbsoluteFill, Html5Audio, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {Blueprint} from "./components/Blueprint";
import {SpeechBubble, sceneIndexAt} from "./components/Captions";
import {prog} from "./components/Draw";
import {Mascot} from "./components/Mascot";
import {TitleBlock} from "./components/TitleBlock";
import {ensureFonts} from "./fonts";
import {SceneVisual} from "./scenes";
import {LAYOUT, defaultTheme} from "./theme";
import type {Scene, ShortProps} from "./types";

ensureFonts();

export const sceneStarts = (scenes: Scene[]) => {
  let acc = 0;
  return scenes.map((s) => {
    const start = acc;
    acc += s.durationInFrames;
    return start;
  });
};

export const mouthAt = (scene: Scene | undefined, local: number) => {
  if (!scene || !scene.mouth.length) return 0;
  const at = (k: number) => scene.mouth[Math.min(scene.mouth.length - 1, Math.max(0, k))] ?? 0;
  return (at(local - 1) + 2 * at(local) + at(local + 1)) / 4;
};

export const NewsShort: React.FC<ShortProps> = (input) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const theme = {...defaultTheme, ...input.theme};
  const props = {...input, theme};
  const {scenes} = props;
  const starts = useMemo(() => sceneStarts(scenes), [scenes]);

  const i = sceneIndexAt(starts, frame);
  const scene = scenes[i];
  const mouth = mouthAt(scene, frame - (starts[i] ?? 0));

  // Byte hops when a new sheet starts.
  const sinceSheet = frame - (starts[i] ?? 0);
  const hopP = i > 0 ? spring({frame: sinceSheet, fps, config: {damping: 9, stiffness: 160, mass: 0.6}}) : 1;
  const hop = -Math.sin(Math.min(1, hopP) * Math.PI) * 22;

  const m = LAYOUT.mascot;
  const hook = scenes[0];
  const hookHasTag = hook?.visual.type === "headline" && Boolean(hook.visual.tag);

  return (
    <AbsoluteFill style={{backgroundColor: theme.bg, overflow: "hidden"}}>
      <Blueprint theme={theme} sceneStarts={starts} />

      {scenes.map((s, k) => (
        <Sequence key={s.id} from={starts[k]} durationInFrames={s.durationInFrames} name={`${k + 1}. ${s.visual.type}`}>
          <SceneVisual scene={s} theme={theme} brand={props.brand.name} />
          {s.audio ? <Html5Audio src={staticFile(s.audio)} /> : null}
        </Sequence>
      ))}

      <TitleBlock props={props} sheet={i + 1} sheetStart={starts[i] ?? 0} />

      {props.captions.enabled ? (
        <SpeechBubble scenes={scenes} starts={starts} theme={theme} maxWords={props.captions.maxWords} maxChars={props.captions.maxChars} />
      ) : null}

      <div style={{position: "absolute", left: m.x, top: m.y + hop, width: m.size, height: (m.size * 300) / 260}}>
        <Mascot theme={theme} mouth={mouth} talking={mouth > 0.08} drawP={prog(frame, 2, 24)} />
      </div>

      {props.sfx.swish
        ? starts.slice(1).map((f, k) => (
            <Sequence key={`swish-${k}`} from={Math.max(0, f - 2)} durationInFrames={24} name="swish">
              <Html5Audio src={staticFile(props.sfx.swish as string)} volume={0.32} />
            </Sequence>
          ))
        : null}
      {props.sfx.stamp && hookHasTag ? (
        <Sequence from={21} durationInFrames={20} name="stamp">
          <Html5Audio src={staticFile(props.sfx.stamp)} volume={0.5} />
        </Sequence>
      ) : null}
      {props.music ? <Html5Audio src={staticFile(props.music.src)} volume={props.music.volume} loop /> : null}
    </AbsoluteFill>
  );
};
