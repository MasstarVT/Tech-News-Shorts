import React from "react";
import {Easing, useCurrentFrame} from "remotion";
import {prog} from "../components/Draw";
import {DISPLAY, TEXT} from "../fonts";
import type {Theme} from "../types";
import {AREA_W, DimensionLine, DrawingArea, fitSize} from "./common";

/** Closing sheet: the channel name drawn large, with the sign-off line under it. */
export const OutroScene: React.FC<{text: string; brand: string; theme: Theme; durationInFrames: number}> = ({
  text,
  brand,
  theme,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const wipe = prog(frame, 2, 16, Easing.out(Easing.cubic));
  const dimP = prog(frame, 12, 14);
  const textP = prog(frame, 18, 12, Easing.out(Easing.cubic));
  const brandSize = fitSize(brand, [[8, 210], [12, 170], [18, 130]], 104);
  const size = fitSize(text, [[22, 64], [36, 56]], 50);
  return (
    <DrawingArea durationInFrames={durationInFrames} style={{display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"}}>
      <div
        style={{
          fontFamily: DISPLAY,
          fontWeight: 900,
          fontSize: brandSize,
          lineHeight: 0.9,
          color: theme.line,
          clipPath: `inset(-15% ${(1 - wipe) * 100}% -15% 0)`,
          textShadow: `0 8px 0 ${theme.ink}`,
          whiteSpace: "nowrap",
        }}
      >
        {brand}
      </div>
      <svg width={AREA_W} height={80} style={{overflow: "visible", marginTop: 10}}>
        <DimensionLine x1={90} x2={AREA_W - 90} y={40} p={dimP} color={theme.draft} />
      </svg>
      <div
        style={{
          marginTop: 18,
          maxWidth: 820,
          textAlign: "center",
          fontFamily: TEXT,
          fontWeight: 600,
          fontSize: size,
          lineHeight: 1.15,
          color: theme.accent,
          opacity: textP,
          transform: `translateY(${(1 - textP) * 20}px)`,
          textWrap: "balance",
        }}
      >
        {text}
      </div>
    </DrawingArea>
  );
};
