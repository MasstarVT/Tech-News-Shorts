import React from "react";
import {Easing, useCurrentFrame} from "remotion";
import {Drawn, DrawnIcon, prog} from "../components/Draw";
import {DISPLAY} from "../fonts";
import {iconNode} from "../icons";
import type {Theme} from "../types";
import {AREA_W, DrawingArea, fitSize} from "./common";

/** A detail callout: a circle around a line icon, with a leader line down to the label. */
export const IconScene: React.FC<{
  icon: string;
  text: string;
  theme: Theme;
  durationInFrames: number;
}> = ({icon, text, theme, durationInFrames}) => {
  const frame = useCurrentFrame();
  const cx = AREA_W / 2;
  const cy = 246;
  const r = 190;
  const circleP = prog(frame, 1, 16);
  const iconP = prog(frame, 8, 26, Easing.inOut(Easing.quad));
  const leaderP = prog(frame, 18, 8);
  const textP = prog(frame, 22, 10);
  const size = fitSize(text, [[18, 92], [30, 80], [46, 68]], 58);
  const ticks = [0, 90, 180, 270];

  return (
    <DrawingArea durationInFrames={durationInFrames}>
      <svg width={AREA_W} height={520} style={{position: "absolute", left: 0, top: 0, overflow: "visible"}}>
        <Drawn tag="circle" p={circleP} attrs={{cx, cy, r, fill: theme.ink, fillOpacity: 0.4, stroke: theme.line, strokeWidth: 5}} />
        <Drawn tag="circle" p={circleP} fillP={0} attrs={{cx, cy, r: r + 22, stroke: theme.draft, strokeWidth: 2, strokeDasharray: "6 10"}} />
        {ticks.map((deg, i) => {
          const a = (deg * Math.PI) / 180;
          return (
            <Drawn
              key={deg}
              tag="line"
              p={prog(frame, 10 + i * 2, 6)}
              attrs={{
                x1: cx + Math.cos(a) * (r - 18),
                y1: cy + Math.sin(a) * (r - 18),
                x2: cx + Math.cos(a) * (r + 40),
                y2: cy + Math.sin(a) * (r + 40),
                stroke: theme.draft,
                strokeWidth: 4,
                strokeLinecap: "round",
              }}
            />
          );
        })}
        <Drawn tag="line" p={leaderP} attrs={{x1: cx, y1: cy + r + 40, x2: cx, y2: cy + r + 70, stroke: theme.draft, strokeWidth: 4}} />
      </svg>
      <div style={{position: "absolute", left: cx - 125, top: cy - 125}}>
        <DrawnIcon node={iconNode(icon)} p={iconP} size={250} color={theme.line} strokeWidth={1.5} />
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          top: cy + r + 82,
          width: AREA_W,
          textAlign: "center",
          fontFamily: DISPLAY,
          fontWeight: 700,
          fontSize: size,
          lineHeight: 1.0,
          color: theme.line,
          opacity: textP,
          transform: `translateY(${(1 - textP) * 16}px)`,
          textWrap: "balance",
          textShadow: `0 5px 0 ${theme.ink}`,
        }}
      >
        {text}
      </div>
    </DrawingArea>
  );
};
