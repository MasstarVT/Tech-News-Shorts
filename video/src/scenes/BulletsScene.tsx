import React from "react";
import {useCurrentFrame} from "remotion";
import {Drawn, prog} from "../components/Draw";
import {DISPLAY} from "../fonts";
import type {Theme} from "../types";
import {AREA_H, AREA_W, DrawingArea, fitSize} from "./common";

/** A short checklist; each item is ticked off in turn while it is talked about. */
export const BulletsScene: React.FC<{
  items: string[];
  theme: Theme;
  durationInFrames: number;
}> = ({items, theme, durationInFrames}) => {
  const frame = useCurrentFrame();
  const list = items.slice(0, 4);
  const n = Math.max(1, list.length);
  const rowH = Math.min(n <= 2 ? 250 : 200, (AREA_H - 40) / n);
  const top = (AREA_H - rowH * n) / 2;
  const span = (durationInFrames * 0.75) / n;
  const longest = list.reduce((a, b) => (b.length > a.length ? b : a), "");
  // Items may wrap onto two lines, so sizes stay big even for longer items.
  const size = fitSize(longest, [[14, 92], [22, 84], [32, 76]], 66);

  return (
    <DrawingArea durationInFrames={durationInFrames}>
      {list.map((item, i) => {
        const start = 3 + i * span;
        const boxP = prog(frame, start, 9);
        const tickP = prog(frame, start + 7, 8);
        const textP = prog(frame, start + 3, 9);
        const y = top + i * rowH;
        return (
          <div key={i} style={{position: "absolute", left: 0, top: y, width: AREA_W, height: rowH, display: "flex", alignItems: "center"}}>
            <svg width={96} height={96} viewBox="0 0 96 96" style={{flexShrink: 0, overflow: "visible"}}>
              <Drawn tag="rect" p={boxP} attrs={{x: 14, y: 14, width: 68, height: 68, rx: 12, fill: theme.ink, fillOpacity: 0.5, stroke: theme.line, strokeWidth: 5}} />
              <Drawn tag="polyline" p={tickP} attrs={{points: "28,50 43,64 70,32", stroke: theme.accent, strokeWidth: 9, strokeLinecap: "round", strokeLinejoin: "round"}} />
            </svg>
            <div
              style={{
                marginLeft: 26,
                maxWidth: AREA_W - 130,
                fontFamily: DISPLAY,
                fontWeight: 700,
                fontSize: size,
                lineHeight: 0.98,
                textWrap: "balance",
                color: theme.line,
                opacity: textP,
                transform: `translateX(${(1 - textP) * 24}px)`,
                textShadow: `0 5px 0 ${theme.ink}`,
              }}
            >
              {item}
            </div>
          </div>
        );
      })}
    </DrawingArea>
  );
};
