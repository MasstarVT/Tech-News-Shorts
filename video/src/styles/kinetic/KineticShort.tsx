import React, {useMemo} from "react";
import {AbsoluteFill, Html5Audio, Sequence, staticFile, useCurrentFrame} from "remotion";
import {sceneIndexAt} from "../../components/Captions";
import {ensureFonts} from "../../fonts";
import {mouthAt, sceneStarts} from "../../NewsShort";
import {defaultTheme} from "../../theme";
import type {ShortProps} from "../../types";
import {Background, Captions, Header, Progress, Wipes, palette, sceneTints} from "./parts";
import {SceneVisual, Stage} from "./scenes";

ensureFonts();

/** Kinetic style: karaoke captions, springy scene graphics, colour wipes between scenes. */
export const KineticShort: React.FC<ShortProps> = (input) => {
  const frame = useCurrentFrame();
  const theme = {...defaultTheme, ...input.theme};
  const {scenes} = input;
  const p = palette(theme);
  const starts = useMemo(() => sceneStarts(scenes), [scenes]);
  const tints = sceneTints(p, scenes.length);
  const i = sceneIndexAt(starts, frame);
  const mouth = mouthAt(scenes[i], frame - (starts[i] ?? 0));
  const hookHasTag = scenes[0]?.visual.type === "headline" && Boolean(scenes[0].visual.tag);

  return (
    <AbsoluteFill style={{backgroundColor: p.bg, overflow: "hidden"}}>
      <Background p={p} tints={tints} starts={starts} />

      {scenes.map((s, k) => (
        <Sequence key={s.id} from={starts[k]} durationInFrames={s.durationInFrames} name={`${k + 1}. ${s.visual.type}`}>
          <Stage d={s.durationInFrames}>
            <SceneVisual scene={s} p={p} tint={tints[k]} brand={input.brand.name} theme={theme} />
          </Stage>
          {s.audio ? <Html5Audio src={staticFile(s.audio)} /> : null}
        </Sequence>
      ))}

      <Wipes starts={starts} tints={tints} p={p} />
      <Header props={{...input, theme}} p={p} tint={tints[i]} mouth={mouth} />
      <Progress scenes={scenes} starts={starts} tint={tints[i]} p={p} />
      {input.captions.enabled ? (
        <Captions scenes={scenes} starts={starts} p={p} tints={tints} maxWords={input.captions.maxWords} maxChars={input.captions.maxChars} />
      ) : null}

      {input.sfx.swish
        ? starts.slice(1).map((f, k) => (
            <Sequence key={`swish-${k}`} from={Math.max(0, f - 6)} durationInFrames={24} name="swish">
              <Html5Audio src={staticFile(input.sfx.swish as string)} volume={0.36} />
            </Sequence>
          ))
        : null}
      {input.sfx.stamp && hookHasTag ? (
        <Sequence from={15} durationInFrames={20} name="stamp">
          <Html5Audio src={staticFile(input.sfx.stamp)} volume={0.5} />
        </Sequence>
      ) : null}
      {input.music ? <Html5Audio src={staticFile(input.music.src)} volume={input.music.volume} loop /> : null}
    </AbsoluteFill>
  );
};
