// Renders one job: node render.mjs --props <props.json> --public-dir <job folder> --out <video.mp4>
// Optional: --still <frame> (writes a PNG instead), --browser <chrome-headless-shell path>,
//           --concurrency <n|50%>, --crf <n>, --gl <angle|egl|swiftshader|...>
// Prints one JSON object per line ({"stage": ..., "progress": 0..1}) so the Python side can show progress.

import {bundle} from "@remotion/bundler";
import {ensureBrowser, renderMedia, renderStill, selectComposition} from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

const parseArgs = (argv) => {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) continue;
    const key = a.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    const next = argv[i + 1];
    if (next === undefined || next.startsWith("--")) out[key] = true;
    else {
      out[key] = next;
      i++;
    }
  }
  return out;
};

const log = (obj) => process.stdout.write(`${JSON.stringify(obj)}\n`);

const main = async () => {
  const args = parseArgs(process.argv.slice(2));
  if (!args.out) {
    console.error("usage: node render.mjs --props props.json --public-dir <dir> --out video.mp4 [--still N]");
    process.exit(2);
  }
  // Without --props the composition's sample props are used (handy for checking the design).
  const inputProps = args.props ? JSON.parse(fs.readFileSync(args.props, "utf8")) : {};
  const browserExecutable = args.browser || process.env.REMOTION_BROWSER_EXECUTABLE || null;
  const chromiumOptions = args.gl ? {gl: args.gl} : {};

  let lastBundle = -1;
  const serveUrl = await bundle({
    entryPoint: path.join(here, "src", "index.ts"),
    publicDir: args.publicDir ? path.resolve(args.publicDir) : null,
    onProgress: (p) => {
      const step = Math.floor(p / 10);
      if (step !== lastBundle) {
        lastBundle = step;
        log({stage: "bundle", progress: p / 100});
      }
    },
  });

  // First run on a new machine downloads chrome-headless-shell (~100 MB); report it instead of hanging silently.
  const onBrowserDownload = () => {
    log({stage: "browser-download", progress: 0});
    return {version: null, onProgress: ({percent}) => log({stage: "browser-download", progress: percent})};
  };
  await ensureBrowser({browserExecutable, onBrowserDownload});

  const composition = await selectComposition({
    serveUrl,
    id: args.composition || "NewsShort",
    inputProps,
    browserExecutable,
    chromiumOptions,
  });
  log({stage: "composition", durationInFrames: composition.durationInFrames, fps: composition.fps});

  fs.mkdirSync(path.dirname(path.resolve(args.out)), {recursive: true});

  if (args.still !== undefined) {
    // --still 40 writes one PNG to --out; --still 10,80,200 writes frame-NNNN.png files into the --out folder.
    const frames = String(args.still)
      .split(",")
      .map((f) => Math.min(composition.durationInFrames - 1, Math.max(0, Number(f) || 0)));
    const many = frames.length > 1;
    if (many) fs.mkdirSync(path.resolve(args.out), {recursive: true});
    for (const frame of frames) {
      const output = many ? path.join(path.resolve(args.out), `frame-${String(frame).padStart(4, "0")}.png`) : path.resolve(args.out);
      await renderStill({composition, serveUrl, output, frame, inputProps, browserExecutable, chromiumOptions, imageFormat: "png"});
      log({stage: "still", out: output, frame});
    }
    log({stage: "done", out: path.resolve(args.out)});
    return;
  }

  let lastPct = -1;
  await renderMedia({
    composition,
    serveUrl,
    codec: "h264",
    outputLocation: path.resolve(args.out),
    inputProps,
    browserExecutable,
    chromiumOptions,
    concurrency: args.concurrency ? (String(args.concurrency).endsWith("%") ? args.concurrency : Number(args.concurrency)) : null,
    crf: args.crf ? Number(args.crf) : 23,
    pixelFormat: "yuv420p",
    audioCodec: "aac",
    audioBitrate: "192k",
    overwrite: true,
    onBrowserDownload,
    onProgress: ({progress, renderedFrames, encodedFrames}) => {
      const pct = Math.floor(progress * 100);
      if (pct !== lastPct) {
        lastPct = pct;
        log({stage: "render", progress, renderedFrames, encodedFrames});
      }
    },
  });
  log({stage: "done", out: path.resolve(args.out)});
};

main().catch((err) => {
  log({stage: "error", message: String(err?.stack || err)});
  process.exit(1);
});
