import {FPS, defaultTheme} from "./theme";
import type {Scene, ShortProps, Visual, Word} from "./types";

// Placeholder content for Remotion Studio (`npm run studio`). Real renders get props from the Python pipeline.

const scene = (id: string, narration: string, visual: Visual): Scene => {
  const words = narration.split(/\s+/).filter(Boolean);
  const msPerWord = 330;
  const timed: Word[] = words.map((text, k) => ({text, startMs: 150 + k * msPerWord, endMs: 150 + k * msPerWord + 280}));
  const durationMs = 150 + words.length * msPerWord + 450;
  const durationInFrames = Math.round((durationMs / 1000) * FPS);
  const mouth = Array.from({length: durationInFrames}, (_, f) => {
    const t = (f / FPS) * 1000;
    const w = timed.find((x) => t >= x.startMs && t <= x.endMs);
    return w ? Math.abs(Math.sin(((t - w.startMs) / 280) * Math.PI)) * 0.9 : 0;
  });
  return {id, durationInFrames, audio: null, words: timed, mouth, visual};
};

export const sampleProps: ShortProps = {
  brand: {name: "Byte Brief"},
  story: {source: "Sample", date: "Oct 20", topic: "Chips"},
  theme: defaultTheme,
  scenes: [
    scene("s0", "This is a sample story, so you can preview the look.", {type: "headline", text: "A sample headline for the preview", tag: "Chips"}),
    scene("s1", "Numbers get their own sheet and count up.", {type: "stat", value: "$4.2B", label: "a sample number", trend: "up"}),
    scene("s2", "Ideas get a drawn icon with a short label.", {type: "icon", icon: "chip", text: "Icons are drawn line by line"}),
    scene("s3", "Comparisons go side by side.", {type: "versus", left: "Old way", right: "New way", label: "what changes"}),
    scene("s4", "And lists get ticked off one by one.", {type: "bullets", items: ["First point", "Second point", "Third point"]}),
    scene("s5", "Follow for tomorrow's brief.", {type: "outro", text: "Follow for tomorrow's brief"}),
  ],
  sfx: {swish: null, stamp: null},
  music: null,
  captions: {enabled: true, maxWords: 3, maxChars: 16},
};
