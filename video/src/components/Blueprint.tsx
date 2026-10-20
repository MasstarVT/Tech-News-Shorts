import React from "react";
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {HEIGHT, WIDTH} from "../theme";
import type {Theme} from "../types";

const MINOR = 36;
const MAJOR = MINOR * 5;
const SHEET_SHIFT = MAJOR; // the paper slides one major square per scene change

/** Drafting-paper background: grid that drifts slowly and slides up on every scene change. */
export const Blueprint: React.FC<{theme: Theme; sceneStarts: number[]}> = ({theme, sceneStarts}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  let offset = frame * 0.5;
  for (const start of sceneStarts.slice(1)) {
    offset += SHEET_SHIFT * spring({frame: frame - start, fps, config: {damping: 20, stiffness: 110, mass: 0.9}});
  }
  const y = -(offset % MAJOR);

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(120% 85% at 50% 38%, ${theme.bg} 0%, ${theme.bg} 42%, ${theme.bgDeep} 100%)`,
      }}
    >
      <svg width={WIDTH} height={HEIGHT} style={{position: "absolute", inset: 0}}>
        <defs>
          <pattern id="bp-minor" width={MINOR} height={MINOR} patternUnits="userSpaceOnUse" patternTransform={`translate(0 ${y})`}>
            <path d={`M ${MINOR} 0 L 0 0 0 ${MINOR}`} fill="none" stroke={theme.line} strokeOpacity={0.07} strokeWidth={1.5} />
          </pattern>
          <pattern id="bp-major" width={MAJOR} height={MAJOR} patternUnits="userSpaceOnUse" patternTransform={`translate(0 ${y})`}>
            <path d={`M ${MAJOR} 0 L 0 0 0 ${MAJOR}`} fill="none" stroke={theme.line} strokeOpacity={0.15} strokeWidth={2} />
          </pattern>
        </defs>
        <rect width={WIDTH} height={HEIGHT} fill="url(#bp-minor)" />
        <rect width={WIDTH} height={HEIGHT} fill="url(#bp-major)" />
        {/* sheet border */}
        <rect x={34} y={34} width={WIDTH - 68} height={HEIGHT - 68} fill="none" stroke={theme.line} strokeOpacity={0.22} strokeWidth={2} />
      </svg>
    </AbsoluteFill>
  );
};
