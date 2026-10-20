import React from "react";
import {Composition} from "remotion";
import {NewsShort} from "./NewsShort";
import {sampleProps} from "./sample-props";
import {KineticShort} from "./styles/kinetic/KineticShort";
import {SlideshowShort} from "./styles/slideshow/SlideshowShort";
import {FPS, HEIGHT, WIDTH} from "./theme";
import type {ShortProps} from "./types";

const metadata = ({props}: {props: ShortProps}) => ({
  durationInFrames: Math.max(1, props.scenes.reduce((sum, s) => sum + s.durationInFrames, 0)),
});

// One composition per style, all on the same props. render.mjs picks one with --composition
// (the Python side maps render.style to these ids).
export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="NewsShort"
      component={NewsShort}
      width={WIDTH}
      height={HEIGHT}
      fps={FPS}
      durationInFrames={FPS * 30}
      defaultProps={sampleProps}
      calculateMetadata={metadata}
    />
    <Composition
      id="NewsShortKinetic"
      component={KineticShort}
      width={WIDTH}
      height={HEIGHT}
      fps={FPS}
      durationInFrames={FPS * 30}
      defaultProps={sampleProps}
      calculateMetadata={metadata}
    />
    <Composition
      id="NewsShortSlideshow"
      component={SlideshowShort}
      width={WIDTH}
      height={HEIGHT}
      fps={FPS}
      durationInFrames={FPS * 30}
      defaultProps={sampleProps}
      calculateMetadata={metadata}
    />
  </>
);
