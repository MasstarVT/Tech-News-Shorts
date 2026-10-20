import React from "react";
import {random, useCurrentFrame} from "remotion";
import type {Theme} from "../types";
import {Drawn} from "./Draw";

/** Frames (out of every ~4 s) where Byte's eyes are closed. Deterministic so renders are repeatable. */
const blinkAmount = (frame: number) => {
  const period = 120;
  const cycle = Math.floor(frame / period);
  const at = 20 + Math.floor(random(`blink-${cycle}`) * 80);
  const d = frame - cycle * period - at;
  if (d < 0 || d > 5) return 1;
  return [0.6, 0.15, 0.08, 0.15, 0.6, 1][d];
};

/**
 * Byte, the channel's line-drawn robot anchor. 260 x 300 artboard.
 * `mouth` is 0..1 openness from the narration; `drawP` draws the figure in.
 */
export const Mascot: React.FC<{
  theme: Theme;
  mouth: number;
  talking: boolean;
  drawP: number;
  lookX?: number;
}> = ({theme, mouth, talking, drawP, lookX = 1}) => {
  const frame = useCurrentFrame();
  const bob = Math.sin((frame / 70) * Math.PI * 2) * 5 - mouth * 5;
  const tilt = Math.sin((frame / 150) * Math.PI * 2) * 2.2;
  const blink = blinkAmount(frame);
  const m = Math.min(1, Math.max(0, mouth));

  const mouthW = 50 + 14 * m;
  const mouthH = 7 + 34 * m;
  const fillP = Math.min(1, drawP * 1.4);
  const stroke = {stroke: theme.line, strokeLinecap: "round" as const, strokeLinejoin: "round" as const};

  return (
    <svg viewBox="0 0 260 300" width="100%" height="100%" style={{overflow: "visible"}}>
      <g transform={`translate(0 ${bob}) rotate(${tilt} 130 260)`}>
        {/* antenna */}
        <Drawn tag="line" p={drawP} attrs={{x1: 130, y1: 60, x2: 130, y2: 26, ...stroke, strokeWidth: 6}} />
        <Drawn
          tag="circle"
          p={drawP}
          fillP={fillP}
          attrs={{cx: 130, cy: 18, r: 11, fill: talking ? theme.accent : theme.draft, ...stroke, strokeWidth: 5}}
        />
        {/* body */}
        <Drawn
          tag="path"
          p={drawP}
          fillP={fillP}
          attrs={{d: "M 34 300 Q 36 252 92 246 L 168 246 Q 224 252 226 300", fill: theme.ink, ...stroke, strokeWidth: 7}}
        />
        <Drawn tag="rect" p={drawP} fillP={fillP} attrs={{x: 110, y: 226, width: 40, height: 24, fill: theme.ink, ...stroke, strokeWidth: 6}} />
        {/* ears */}
        <Drawn tag="rect" p={drawP} fillP={fillP} attrs={{x: 4, y: 112, width: 20, height: 58, rx: 8, fill: theme.ink, ...stroke, strokeWidth: 6}} />
        <Drawn tag="rect" p={drawP} fillP={fillP} attrs={{x: 236, y: 112, width: 20, height: 58, rx: 8, fill: theme.ink, ...stroke, strokeWidth: 6}} />
        {/* head + screen */}
        <Drawn
          tag="rect"
          p={drawP}
          fillP={fillP}
          attrs={{x: 20, y: 58, width: 220, height: 172, rx: 42, fill: theme.ink, ...stroke, strokeWidth: 7}}
        />
        <Drawn
          tag="rect"
          p={drawP}
          fillP={fillP}
          attrs={{x: 40, y: 78, width: 180, height: 132, rx: 28, fill: "#173A6B", stroke: theme.draft, strokeWidth: 3}}
        />
        {fillP > 0.6 && (
          <g opacity={(fillP - 0.6) / 0.4}>
            {/* eyes */}
            {[96, 164].map((cx) => (
              <g key={cx} transform={`translate(${cx} 128) scale(1 ${blink})`}>
                <ellipse cx={0} cy={0} rx={17} ry={21} fill={theme.line} />
                <circle cx={4 * lookX} cy={-3} r={7.5} fill={theme.ink} />
              </g>
            ))}
            {/* mouth */}
            <rect
              x={130 - mouthW / 2}
              y={180 - mouthH / 2}
              width={mouthW}
              height={mouthH}
              rx={Math.min(mouthH / 2, 16)}
              fill={theme.ink}
              stroke={theme.line}
              strokeWidth={5}
            />
          </g>
        )}
      </g>
    </svg>
  );
};
