import * as lucide from "lucide";
import type {IconNode} from "./components/Draw";
import names from "./icons.json";

// Friendly icon names the script writer may use (shared with Python via icons.json) -> lucide icons.
const MAP = names as Record<string, string>;
const lib = lucide as unknown as Record<string, IconNode | undefined>;

export const ICON_NAMES = Object.keys(MAP);

export const iconNode = (name: string): IconNode => {
  const key = MAP[name?.toLowerCase?.() ?? ""] ?? MAP.news;
  return lib[key] ?? (lib.Newspaper as IconNode);
};
