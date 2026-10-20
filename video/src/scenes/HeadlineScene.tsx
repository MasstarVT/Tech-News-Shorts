import React from "react";
import {Easing, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {prog} from "../components/Draw";
import {DISPLAY} from "../fonts";
import type {Theme} from "../types";
import {DrawingArea, headlineSize} from "./common";

const Bracket: React.FC<{corner: "tl" | "tr" | "bl" | "br"; p: number; color: string}> = ({corner, p, color}) => {
  const size = 46;
  const rot = {tl: 0, tr: 90, br: 180, bl: 270}[corner];
  const pos: React.CSSProperties = {
    tl: {left: 0, top: 0},
    tr: {right: 0, top: 0},
    br: {right: 0, bottom: 0},
    bl: {left: 0, bottom: 0},
  }[corner];
  return (
    <div
      style={{
        position: "absolute",
        width: size,
        height: size,
        borderTop: `5px solid ${color}`,
        borderLeft: `5px solid ${color}`,
        transform: `rotate(${rot}deg) scale(${p})`,
        transformOrigin: "50% 50%",
        opacity: p,
        ...pos,
      }}
    />
  );
};

export const HeadlineScene: React.FC<{
  text: string;
  tag?: string;
  theme: Theme;
  durationInFrames: number;
}> = ({text, tag, theme, durationInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const size = headlineSize(text);
  const lineP = prog(frame, 2, 14);
  const wipe = prog(frame, 7, 16, Easing.out(Easing.cubic));
  const bracketP = prog(frame, 16, 10, Easing.out(Easing.back(1.6)));
  const stamp = spring({frame: frame - 20, fps, config: {damping: 11, stiffness: 190, mass: 0.7}});

  return (
    <DrawingArea durationInFrames={durationInFrames} style={{display: "flex", flexDirection: "column", justifyContent: "center"}}>
      <div style={{position: "relative", padding: "56px 48px 56px 84px"}}>
        {/* height dimension along the left edge */}
        <div style={{position: "absolute", left: 30, top: 56, bottom: 56, width: 4, background: theme.draft, transform: `scaleY(${lineP})`, transformOrigin: "50% 0"}} />
        <div style={{position: "absolute", left: 14, top: 54, width: 36, height: 4, background: theme.draft, opacity: lineP}} />
        <div style={{position: "absolute", left: 14, bottom: 54, width: 36, height: 4, background: theme.draft, opacity: lineP > 0.98 ? 1 : 0}} />
        <div
          style={{
            fontFamily: DISPLAY,
            fontWeight: 800,
            fontSize: size,
            lineHeight: 0.98,
            color: theme.line,
            textWrap: "balance",
            clipPath: `inset(-12% ${(1 - wipe) * 100}% -12% 0)`,
            textShadow: `0 6px 0 ${theme.ink}`,
          }}
        >
          {text}
        </div>
        {(["tl", "tr", "bl", "br"] as const).map((c) => (
          <Bracket key={c} corner={c} p={bracketP} color={theme.line} />
        ))}
      </div>
      {tag ? (
        <div
          style={{
            position: "absolute",
            right: 26,
            top: 6,
            transform: `rotate(-8deg) scale(${2.1 - 1.1 * stamp})`,
            opacity: Math.min(1, stamp * 1.6),
            border: `6px solid ${theme.alert}`,
            borderRadius: 10,
            padding: "4px 20px 2px",
            fontFamily: DISPLAY,
            fontWeight: 800,
            fontSize: 54,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: theme.alert,
            background: `${theme.ink}88`,
          }}
        >
          {tag}
        </div>
      ) : null}
    </DrawingArea>
  );
};
