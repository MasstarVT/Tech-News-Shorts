import React from "react";
import {spring, useCurrentFrame, useVideoConfig} from "remotion";
import {Drawn, prog} from "../components/Draw";
import {DISPLAY, TEXT} from "../fonts";
import type {Theme} from "../types";
import {AREA_W, DrawingArea, fitSize} from "./common";

export const VersusScene: React.FC<{
  left: string;
  right: string;
  label?: string;
  theme: Theme;
  durationInFrames: number;
}> = ({left, right, label, theme, durationInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const boxW = 404;
  const boxH = 310;
  const top = 60;
  const leftP = prog(frame, 1, 14);
  const rightP = prog(frame, 9, 14);
  const vs = spring({frame: frame - 18, fps, config: {damping: 10, stiffness: 200, mass: 0.6}});
  const labelP = prog(frame, 26, 10);
  const longest = left.length > right.length ? left : right;
  const size = fitSize(longest, [[7, 104], [12, 84], [20, 68]], 56);

  const box = (x: number, text: string, p: number) => (
    <>
      <Drawn tag="rect" p={p} attrs={{x, y: top, width: boxW, height: boxH, rx: 22, fill: theme.ink, fillOpacity: 0.45, stroke: theme.line, strokeWidth: 5}} />
      <foreignObject x={x} y={top} width={boxW} height={boxH}>
        <div
          style={{
            width: boxW,
            height: boxH,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            padding: 26,
            boxSizing: "border-box",
            fontFamily: DISPLAY,
            fontWeight: 800,
            fontSize: size,
            lineHeight: 0.98,
            color: theme.line,
            opacity: Math.max(0, (p - 0.5) * 2),
            textWrap: "balance",
          }}
        >
          {text}
        </div>
      </foreignObject>
    </>
  );

  return (
    <DrawingArea durationInFrames={durationInFrames}>
      <svg width={AREA_W} height={520} style={{position: "absolute", left: 0, top: 0, overflow: "visible"}}>
        {box(0, left, leftP)}
        {box(AREA_W - boxW, right, rightP)}
      </svg>
      <div
        style={{
          position: "absolute",
          left: AREA_W / 2 - 62,
          top: top + boxH / 2 - 62,
          width: 124,
          height: 124,
          borderRadius: 62,
          background: theme.accent,
          border: `6px solid ${theme.ink}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: DISPLAY,
          fontWeight: 900,
          fontSize: 62,
          color: theme.ink,
          transform: `scale(${vs}) rotate(${(1 - vs) * -30}deg)`,
        }}
      >
        vs
      </div>
      {label ? (
        <div
          style={{
            position: "absolute",
            left: 0,
            top: top + boxH + 60,
            width: AREA_W,
            textAlign: "center",
            fontFamily: TEXT,
            fontWeight: 600,
            fontSize: 52,
            lineHeight: 1.15,
            color: theme.draft,
            opacity: labelP,
            textWrap: "balance",
          }}
        >
          {label}
        </div>
      ) : null}
    </DrawingArea>
  );
};
