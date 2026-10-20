import React from "react";
import type {Scene, Theme} from "../types";
import {BulletsScene} from "./BulletsScene";
import {HeadlineScene} from "./HeadlineScene";
import {IconScene} from "./IconScene";
import {OutroScene} from "./OutroScene";
import {StatScene} from "./StatScene";
import {VersusScene} from "./VersusScene";

/** Picks the drawing for a scene. New visual types: add the type in types.ts, a scene file, a case here, and the Python schema. */
export const SceneVisual: React.FC<{scene: Scene; theme: Theme; brand: string}> = ({scene, theme, brand}) => {
  const v = scene.visual;
  const d = scene.durationInFrames;
  switch (v.type) {
    case "headline":
      return <HeadlineScene text={v.text} tag={v.tag} theme={theme} durationInFrames={d} />;
    case "stat":
      return <StatScene value={v.value} label={v.label} trend={v.trend} theme={theme} durationInFrames={d} />;
    case "icon":
      return <IconScene icon={v.icon} text={v.text} theme={theme} durationInFrames={d} />;
    case "versus":
      return <VersusScene left={v.left} right={v.right} label={v.label} theme={theme} durationInFrames={d} />;
    case "bullets":
      return <BulletsScene items={v.items} theme={theme} durationInFrames={d} />;
    case "outro":
      return <OutroScene text={v.text} brand={brand} theme={theme} durationInFrames={d} />;
    default:
      return null;
  }
};
