import React from "react";
import {Easing, interpolate} from "remotion";

/** 0 -> 1 between `start` and `start + length` frames. */
export const prog = (
  frame: number,
  start: number,
  length: number,
  easing: (t: number) => number = Easing.inOut(Easing.cubic),
) =>
  interpolate(frame, [start, start + Math.max(1, length)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing,
  });

type Tag = "path" | "rect" | "circle" | "ellipse" | "line" | "polyline" | "polygon";

type DrawnProps = {
  tag: Tag;
  /** Stroke progress, 0 (hidden) to 1 (fully drawn). */
  p: number;
  /** Fill opacity progress; defaults to following the stroke. */
  fillP?: number;
  attrs: Record<string, string | number | undefined>;
};

/** An SVG shape whose outline draws itself like a pen stroke. */
export const Drawn: React.FC<DrawnProps> = ({tag, p, fillP, attrs}) => {
  if (p <= 0.001) return null;
  const {fill, fillOpacity, ...rest} = attrs;
  const fo = fill && fill !== "none" ? Number(fillOpacity ?? 1) * (fillP ?? p) : undefined;
  return React.createElement(tag, {
    ...rest,
    fill: fill ?? "none",
    fillOpacity: fo,
    pathLength: 1,
    strokeDasharray: 1,
    strokeDashoffset: 1 - p,
  });
};

export type IconNode = [string, Record<string, string>][];

/** A 24x24 line icon (lucide format) drawn element by element. */
export const DrawnIcon: React.FC<{
  node: IconNode;
  p: number;
  size: number;
  color: string;
  strokeWidth?: number;
}> = ({node, p, size, color, strokeWidth = 1.6}) => {
  const n = Math.max(1, node.length);
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{overflow: "visible"}}>
      {node.map(([tag, attrs], i) => {
        // Elements start one after another but overlap, so the icon reads as one gesture.
        const start = (i / n) * 0.55;
        const local = Math.min(1, Math.max(0, (p - start) / 0.45));
        return (
          <Drawn
            key={i}
            tag={tag as Tag}
            p={local}
            attrs={{
              ...attrs,
              fill: "none",
              stroke: color,
              strokeWidth,
              strokeLinecap: "round",
              strokeLinejoin: "round",
            }}
          />
        );
      })}
    </svg>
  );
};

/** Text with a thick navy outline drawn underneath (keeps glyphs crisp, unlike -webkit-text-stroke alone). */
export const OutlinedText: React.FC<{
  children: string;
  color: string;
  outline: string;
  width: number;
  style?: React.CSSProperties;
}> = ({children, color, outline, width, style}) => (
  <span style={{position: "relative", display: "inline-block", ...style}}>
    <span
      aria-hidden
      style={{
        position: "absolute",
        inset: 0,
        color: outline,
        WebkitTextStroke: `${width}px ${outline}`,
      }}
    >
      {children}
    </span>
    <span style={{position: "relative", color}}>{children}</span>
  </span>
);
