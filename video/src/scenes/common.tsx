import React from "react";
import {Easing, interpolate, useCurrentFrame} from "remotion";
import {LAYOUT, SAFE} from "../theme";

/** Positions children in the drawing area and fades them out over the scene's last frames. */
export const DrawingArea: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({durationInFrames, children, style}) => {
  const frame = useCurrentFrame();
  const out = interpolate(frame, [durationInFrames - 7, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.in(Easing.cubic),
  });
  return (
    <div
      style={{
        position: "absolute",
        left: SAFE.left,
        top: LAYOUT.drawing.y,
        width: SAFE.right - SAFE.left,
        height: LAYOUT.drawing.h,
        opacity: 1 - out,
        transform: `translateY(${-28 * out}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const AREA_W = SAFE.right - SAFE.left;
export const AREA_H = LAYOUT.drawing.h;

/** Font size that keeps a headline inside the drawing area. */
export const headlineSize = (text: string) => {
  const n = text.length;
  if (n <= 16) return 168;
  if (n <= 26) return 142;
  if (n <= 40) return 118;
  if (n <= 60) return 100;
  return 86;
};

export const fitSize = (text: string, steps: [number, number][], fallback: number) => {
  for (const [maxLen, size] of steps) {
    if (text.length <= maxLen) return size;
  }
  return fallback;
};

/** Horizontal dimension line with end ticks and arrowheads, as on a technical drawing. */
export const DimensionLine: React.FC<{
  x1: number;
  x2: number;
  y: number;
  p: number;
  color: string;
}> = ({x1, x2, y, p, color}) => {
  const mid = (x1 + x2) / 2;
  const half = ((x2 - x1) / 2) * p;
  const a = 16;
  return (
    <g stroke={color} strokeWidth={3} fill="none" strokeLinecap="round" strokeLinejoin="round" opacity={p > 0 ? 1 : 0}>
      <line x1={mid - half} y1={y} x2={mid + half} y2={y} />
      {p > 0.95 && (
        <>
          <line x1={x1} y1={y - 28} x2={x1} y2={y + 28} />
          <line x1={x2} y1={y - 28} x2={x2} y2={y + 28} />
          <polyline points={`${x1 + a},${y - a / 2} ${x1},${y} ${x1 + a},${y + a / 2}`} />
          <polyline points={`${x2 - a},${y - a / 2} ${x2},${y} ${x2 - a},${y + a / 2}`} />
        </>
      )}
    </g>
  );
};
