import React from "react";
import {Composition} from "remotion";
import {NewsShort} from "./NewsShort";
import {sampleProps} from "./sample-props";
import {FPS, HEIGHT, WIDTH} from "./theme";
import type {ShortProps} from "./types";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="NewsShort"
    component={NewsShort}
    width={WIDTH}
    height={HEIGHT}
    fps={FPS}
    durationInFrames={FPS * 30}
    defaultProps={sampleProps}
    calculateMetadata={({props}: {props: ShortProps}) => ({
      durationInFrames: Math.max(1, props.scenes.reduce((sum, s) => sum + s.durationInFrames, 0)),
    })}
  />
);
