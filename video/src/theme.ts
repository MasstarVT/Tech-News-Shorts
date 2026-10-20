import type {Theme} from "./types";

export const WIDTH = 1080;
export const HEIGHT = 1920;
export const FPS = 30;

// Area that TikTok / YouTube Shorts UI never covers: top bar, the like/comment rail on the right
// (from about y=950 down) and the caption/title block at the bottom.
export const SAFE = {top: 170, left: 70, right: 1010, bottom: 1460, rightRail: 950};

// Vertical bands inside the safe area.
export const LAYOUT = {
  titleBlock: {y: 170, h: 112},
  drawing: {y: 320, h: 680},
  mascot: {x: 44, y: 1096, size: 250},
  bubble: {x: 318, y: 1092, w: 632, h: 268},
};

export const defaultTheme: Theme = {
  bg: "#1D4F91", // cyanotype blue
  bgDeep: "#123667",
  line: "#F2F6FF", // chalk white
  draft: "#9AD4FF", // secondary lines and labels
  accent: "#FFD23F", // marker yellow
  alert: "#FF6B5E", // redline
  ink: "#0B2140", // navy ink for fills and outlines
};
