# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

The pipeline is the existing Python 3.12 package `technews` (uv) plus the Remotion renderer in `video/`. The web GUI frontend is React + Vite (the user's choice), talking to a Python API that lives inside the `technews` package and calls the pipeline functions directly (the same shape as the sibling Clip Creator dashboard, which uses FastAPI). Started with a `technews` CLI command.

## Users

One creator (MasstarVT) running a faceless tech-news shorts channel. Today they use it on their own Windows PC in a desktop browser. Later they want to run it on a VPS and reach it remotely, so the GUI must not assume it is on the same machine as the viewer.

Their job: turn one of today's tech stories into a 30–45 second vertical short and get it onto YouTube Shorts and TikTok, either by reviewing and tweaking each video by hand, or by letting it run on its own.

## Product Purpose

A single place to drive the whole pipeline without the CLI: see today's ranked stories, start a video, watch each stage run, read and edit the script, re-voice and re-render (choosing an animation style), watch the result, and publish. Success means a day's short goes from story to posted in a few minutes of attention, and nothing wrong reaches the channel.

## Positioning

Local-first and fact-guarded: the script is written by a local LLM (Ollama) that may only use facts from the article, a number check swaps unbacked stats and raises warnings, the voice is Kokoro TTS on the CPU with real word timings, and the animation is code-rendered by Remotion from the script. No stock footage, no AI video, no per-video cost.

## Operating Context

- Pipeline stages, each re-runnable on a job: news (RSS feeds + Hacker News, ranked and de-duplicated against history) -> script (`script.json`) -> voice (`voice/` wavs + `timing.json`) -> render (`props.json` -> `video.mp4`) -> publish (export folder, YouTube, TikTok inbox draft, Discord preview webhook).
- A job is a folder under `out/` (`job.json` holds status, per-stage info, and publish results; `log.txt` the run log).
- Stage timing on this PC: script about 1–3 minutes with a local model, voice a few seconds, render about a minute. Work is CPU-bound, so one heavy job runs at a time.
- Two operating modes, both required: **manual** (pick a story, review and edit, then publish) and **automatic** (the `daily` run makes and publishes a video on a schedule, optionally held for approval).
- Animation styles: `kinetic` (default), `blueprint`, `slideshow` (`render.style`).

## Capabilities and Constraints

- Script scenes have narration plus one visual: headline (text, tag), stat (value, label, trend), icon (icon name from `video/src/icons.json`, text), versus (left, right, label), bullets (up to 4 items), outro (text).
- Script warnings (number check, unbacked facts) must stay visible before publishing.
- Never automate posting through a browser. TikTok stays inbox-draft unless the app passes TikTok's audit; YouTube uploads stay private until the Google API project passes its audit.
- Secrets live only in `.env` / `config/secrets/`; the GUI must never display or send them.
- Remote use (VPS) needs access control; local use binds to localhost.
- Undecided: scheduling mechanism for auto mode on a VPS, and whether more than one channel/brand is ever needed.

## Brand Commitments

- Channel name: Byte Brief. Mascot: Byte, a line-drawn robot that narrates the videos.
- The videos' look (kinetic by default: bold karaoke captions, springy graphics, colour wipes) belongs to the videos; the GUI is a tool around them.

## Evidence on Hand

- A real finished job: `out/2026-10-20_microg-free-libre-re-implementation-of-google-s/` with the video in all three styles and side-by-side comparisons.
- No analytics, audience numbers, or publish history yet; do not invent them.

## Product Principles

1. The video is the deliverable: it should always be one click away and shown at its real 9:16 shape.
2. Facts before speed: warnings and the source article are on screen wherever a publish decision is made.
3. Every stage is re-runnable: editing a script and re-rendering is a normal path, not a recovery path.
4. Honest progress: long stages show what is happening and how far along they are; failures show the real error and how to retry.
5. Local-first, remote-ready: nothing assumes the browser is on the server's machine.
