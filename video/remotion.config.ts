import {Config} from "@remotion/cli/config";

// Used by `npm run studio`. Pipeline renders go through render.mjs instead.
Config.setEntryPoint("src/index.ts");
Config.setVideoImageFormat("jpeg");
