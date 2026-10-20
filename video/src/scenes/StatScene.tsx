import React from "react";
import {Easing, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {DrawnIcon, prog} from "../components/Draw";
import {DISPLAY, TEXT} from "../fonts";
import {iconNode} from "../icons";
import type {Theme, Trend} from "../types";
import {AREA_W, DimensionLine, DrawingArea, fitSize} from "./common";

type Parsed = {prefix: string; value: number; decimals: number; commas: boolean; suffix: string};

/** "$5.2B" -> prefix "$", 5.2, suffix "B"; null when there is no number to count up. */
export const parseStat = (raw: string): Parsed | null => {
  const m = raw.trim().match(/^([^\d-]*?)(-?\d[\d,]*(?:\.\d+)?)(.*)$/);
  if (!m) return null;
  const num = m[2];
  const value = Number(num.replace(/,/g, ""));
  if (!Number.isFinite(value)) return null;
  const decimals = num.includes(".") ? num.split(".")[1].length : 0;
  return {prefix: m[1], value, decimals, commas: num.includes(","), suffix: m[3]};
};

const format = (p: Parsed, t: number) => {
  const v = p.value * t;
  const s = v.toLocaleString("en-US", {
    minimumFractionDigits: p.decimals,
    maximumFractionDigits: p.decimals,
    useGrouping: p.commas || Math.abs(p.value) >= 10000,
  });
  return `${p.prefix}${s}${p.suffix}`;
};

export const StatScene: React.FC<{
  value: string;
  label: string;
  trend?: Trend;
  theme: Theme;
  durationInFrames: number;
}> = ({value, label, trend = "none", theme, durationInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const parsed = parseStat(value);
  // A quick count-up (under a second) so in-between numbers never linger on screen.
  const count = prog(frame, 4, Math.min(22, Math.round(durationInFrames * 0.4)), Easing.out(Easing.cubic));
  const shown = parsed ? format(parsed, count) : value;
  const size = fitSize(value, [[3, 330], [5, 290], [7, 230], [9, 190]], 160);
  const enter = spring({frame: frame - 2, fps, config: {damping: 13, stiffness: 160, mass: 0.8}});
  const dimP = prog(frame, 14, 14);
  const labelP = prog(frame, 22, 10);
  const trendP = prog(frame, 10, 22);
  const trendColor = trend === "down" ? theme.alert : theme.accent;

  return (
    <DrawingArea
      durationInFrames={durationInFrames}
      style={{display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"}}
    >
      {trend !== "none" ? (
        <div style={{height: 120, marginBottom: -6}}>
          <DrawnIcon node={iconNode(trend === "down" ? "chart-down" : "chart-up")} p={trendP} size={120} color={trendColor} strokeWidth={2.2} />
        </div>
      ) : null}
      <div
        style={{
          fontFamily: DISPLAY,
          fontWeight: 900,
          fontSize: size,
          lineHeight: 0.9,
          color: theme.accent,
          transform: `scale(${0.6 + 0.4 * enter})`,
          opacity: Math.min(1, enter * 2),
          textShadow: `0 10px 0 ${theme.ink}`,
          fontVariantNumeric: "tabular-nums",
          whiteSpace: "nowrap",
        }}
      >
        {shown}
      </div>
      <svg width={AREA_W} height={90} style={{overflow: "visible", marginTop: 18}}>
        <DimensionLine x1={110} x2={AREA_W - 110} y={45} p={dimP} color={theme.draft} />
      </svg>
      <div
        style={{
          fontFamily: TEXT,
          fontWeight: 600,
          fontSize: 54,
          lineHeight: 1.15,
          color: theme.line,
          textAlign: "center",
          maxWidth: 820,
          marginTop: 10,
          opacity: labelP,
          transform: `translateY(${(1 - labelP) * 14}px)`,
          textWrap: "balance",
        }}
      >
        {label}
      </div>
    </DrawingArea>
  );
};
