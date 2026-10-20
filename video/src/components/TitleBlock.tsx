import React from "react";
import {Easing, interpolate, useCurrentFrame} from "remotion";
import {DISPLAY, TEXT} from "../fonts";
import {LAYOUT, SAFE} from "../theme";
import type {ShortProps} from "../types";
import {Drawn, prog} from "./Draw";

/**
 * The drawing's title block, moved to the top because the bottom of a short belongs to the app UI.
 * Cells: brand | source | date | sheet (scene n of N).
 */
export const TitleBlock: React.FC<{
  props: ShortProps;
  sheet: number;
  sheetStart: number;
}> = ({props, sheet, sheetStart}) => {
  const frame = useCurrentFrame();
  const {theme, brand, story, scenes} = props;
  const x = SAFE.left;
  const y = LAYOUT.titleBlock.y;
  const w = SAFE.right - SAFE.left;
  const h = LAYOUT.titleBlock.h;
  const cells = [372, 284, 156, 128];
  const p = prog(frame, 2, 22);
  const textP = prog(frame, 14, 12);

  const flip = interpolate(frame - sheetStart, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.back(2)),
  });

  let cx = x;
  const dividers = cells.slice(0, -1).map((cw) => {
    cx += cw;
    return cx;
  });

  const label: React.CSSProperties = {
    fontFamily: TEXT,
    fontWeight: 500,
    fontSize: 22,
    color: theme.draft,
    lineHeight: 1,
    marginBottom: 8,
  };
  const value: React.CSSProperties = {
    fontFamily: DISPLAY,
    fontWeight: 700,
    fontSize: 40,
    color: theme.line,
    lineHeight: 1,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  };

  return (
    <>
      <svg width={1080} height={y + h + 10} style={{position: "absolute", left: 0, top: 0}}>
        <Drawn tag="rect" p={p} attrs={{x, y, width: w, height: h, fill: theme.ink, fillOpacity: 0.55, stroke: theme.line, strokeWidth: 3}} />
        {dividers.map((dx, i) => (
          <Drawn key={i} tag="line" p={prog(frame, 10 + i * 3, 10)} attrs={{x1: dx, y1: y, x2: dx, y2: y + h, stroke: theme.line, strokeWidth: 2}} />
        ))}
      </svg>
      <div style={{position: "absolute", left: x, top: y, height: h, display: "flex", opacity: textP}}>
        <div style={{width: cells[0], padding: "0 24px", display: "flex", alignItems: "center"}}>
          <div style={{...value, fontWeight: 800, fontSize: 54, letterSpacing: 0.5}}>{brand.name}</div>
        </div>
        <div style={{width: cells[1], padding: "0 20px", display: "flex", flexDirection: "column", justifyContent: "center"}}>
          <div style={label}>Source</div>
          <div style={value}>{story.source}</div>
        </div>
        <div style={{width: cells[2], padding: "0 18px", display: "flex", flexDirection: "column", justifyContent: "center"}}>
          <div style={label}>Date</div>
          <div style={value}>{story.date}</div>
        </div>
        <div style={{width: cells[3], padding: "0 18px", display: "flex", flexDirection: "column", justifyContent: "center"}}>
          <div style={label}>Sheet</div>
          <div style={{...value, transform: `translateY(${(1 - flip) * 18}px)`, opacity: 0.3 + 0.7 * flip}}>
            {sheet}/{scenes.length}
          </div>
        </div>
      </div>
    </>
  );
};
