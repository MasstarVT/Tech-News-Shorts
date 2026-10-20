# Tech News Shorts

Turns the day's tech news into animated vertical shorts for YouTube Shorts and TikTok:

1. **Picks a story.** It reads tech RSS feeds and the Hacker News front page, groups reports of the same news, and ranks them by freshness, how many outlets cover it, Hacker News points and your topic keywords. Stories it already covered are skipped.
2. **Writes the script.** An LLM of your choice turns the article into 30–45 seconds of narration plus a graphic for each line. The default is a local model through Ollama. It may only use facts from the article, and any stat graphic whose number isn't in the article is replaced.
3. **Narrates it.** With [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) on the CPU, [Chatterbox](https://github.com/resemble-ai/chatterbox) on the GPU or [ElevenLabs](https://elevenlabs.io), every word is timed, so captions and the mascot's mouth stay in sync. Money, model numbers and units are rewritten so they're read correctly ("$5B" → "5 billion dollars", "RTX 5090" → "fifty ninety").
4. **Animates it.** [Remotion](https://www.remotion.dev) renders a 1080×1920 video. The default `kinetic` style:
   - Big captions pop in word by word as they're spoken, with the current word on a colour slab.
   - Each scene gets its own colour and a springy graphic: a headline that rises in, a stat whose digits roll like an odometer, an icon in orbit, a versus slam, or a checklist.
   - A slanted colour wipe hides every cut, and **Byte**, the channel's robot, talks in the header and waves in the outro.
   - Swish and stamp sound effects are synthesized (no licensing).
   - Other styles: `blueprint` (line drawings drawn stroke by stroke, Byte in a speech bubble) and `slideshow` (plain baseline). Set `render.style`, pick it in the web app, or run `technews render --style blueprint`.
5. **Hands it over.** It exports the video plus ready-to-paste captions, posts a preview to Discord so you can review it on your phone, and can upload to YouTube and to TikTok's draft inbox.

## Quick start (Windows)

You need [uv](https://docs.astral.sh/uv/), [Node.js 20+](https://nodejs.org) and, for the default script writer, [Ollama](https://ollama.com) with a model (`ollama pull qwen3:14b`).

```bash
uv sync --all-extras
uv run technews init      # creates config/config.yaml and .env, runs npm install in video/
uv run technews doctor    # checks Node/Remotion, the voice model, Ollama, publishing setup
uv run technews news      # today's ranked stories
uv run technews make      # top story -> out/<date>_<story>/video.mp4
```

The first run downloads the Kokoro voice model (~350 MB) and Remotion's headless Chrome (~100 MB).

## Commands

| Command | What it does |
|---|---|
| `technews web` | Open the web app (see below) |
| `technews news` | Ranked candidate stories for today |
| `technews make` | Story → script → voice → video. `--pick 3` uses the 3rd story, `--url <link>` any article, `--llm null` skips the AI, `--publish` posts when done |
| `technews script / voice / render <job>` | Re-run one stage of a job (`latest` is the default job) |
| `technews still <job> --frames 45,200` | Render single frames to PNG |
| `technews preview <job>` | Open the job in Remotion Studio |
| `technews publish <job> --to export,youtube,tiktok` | Post a finished video (`--dry-run` to test) |
| `technews daily` | Scheduled entry point: make today's video and publish to the enabled targets |
| `technews jobs` | Recent jobs and their status |
| `technews voices` / `technews say "text"` | List voices / audition a line (`--engine chatterbox` to try another engine) |
| `technews setup-chatterbox` | Install the Chatterbox GPU voice into its own venv (~8 GB, plus ~5 GB of models on first use) |
| `technews auth youtube` / `technews auth tiktok` | Connect accounts |

### Web app

`technews web` opens a browser app at http://127.0.0.1:8765 that does everything the commands do:

- **Today**: the ranked wire of stories. Press *Make short* on one, or paste an article link.
- **Jobs / rundown**: each short as a TV-style rundown. Scenes are drawn to their real length, and the row on air lights up while the video plays. Edit narration and graphics, then save; the fact check runs again. Re-record the voice, render in any style, and publish (with a dry run).
- **Auto**: make one short a day at a set time. Either hold it for your approval or publish it straight away.
- **Settings**: default style, voice, speed and script model (written to `config.yaml`, comments kept), plus the `doctor` health checks.

The tally in the top bar shows what's running: *Standby* while writing or voicing, *On air* while rendering or publishing. Only one job runs at a time; the rest queue.

Build the frontend once with `cd web && npm install && npm run build`. For frontend work, run `npm run dev` in `web/` (port 5173, forwards `/api` to `technews web`).

On a server (VPS), set `TECHNEWS_WEB_TOKEN=<long random string>` in `.env` and start it with `technews web --host 0.0.0.0 --no-open`. The app then asks for that token. Put it behind HTTPS (a reverse proxy such as Caddy) before exposing it to the internet. Auto mode only runs while the app is running.

### Fixing a video before posting

Every job is a folder under `out/`. Edit `script.json` (narration, on-screen text, which graphic each line gets), then run `technews voice` and `technews render` again. `technews preview` shows the result live in the browser while you tweak.

## Choosing the script writer

Set `llm.tasks.script` in `config/config.yaml`, or pass `--llm` to a single run:

| `--llm` value | What it uses |
|---|---|
| `ollama:qwen3:14b` | Local model on your GPU (default). Free. |
| `anthropic` / `anthropic:claude-opus-5-5` | Claude. Needs `ANTHROPIC_API_KEY` in `.env`. |
| `openai:<model>` / `gemini:<model>` | GPT / Gemini with `OPENAI_API_KEY` / `GEMINI_API_KEY`. |
| `null` | No AI: a template script from the article's first sentences. |

The LLM layer is the same one Clip Creator uses: structured output, responses cached in `data/llm_cache`, and a spending cap per video for cloud providers.

## Voice

Pick an engine with `voice.engine` in `config.yaml` (or on the Settings page):

| Engine | Sound | Runs on | Setup |
|---|---|---|---|
| `kokoro` (default) | Clean, a little flat | CPU, offline | Nothing; downloads ~350 MB on first use |
| `chatterbox` | Expressive, close to a real narrator | GPU (RTX 20-50 series), offline | `technews setup-chatterbox` (~13 GB with models) |
| `elevenlabs` | The most lifelike | ElevenLabs API, paid per character | `ELEVENLABS_API_KEY` in `.env` |

- **Kokoro**: `af_heart` at speed 1.05. `technews voices` lists the others: `am_michael`, `am_fenrir` and `am_puck` are good US male voices, and `bf_emma` and `bm_george` are UK voices. Blend two with `af_heart:0.7+af_bella:0.3`.
- **Chatterbox**: Resemble AI's MIT-licensed model, run in `data/venvs/chatterbox` so its pinned torch doesn't touch the app. Every take is aligned with a speech recogniser. Takes that skip words or get a number wrong are re-recorded, and anything still off is flagged before posting. `model: turbo` is faster. Its built-in voice talks fast, so the standard model is slowed to `pace: 0.85` without changing pitch. To clone a voice, put 10-20 s of one clean speaker in `data/voices/` and pick it (only voices you have the right to use). Ollama's model is unloaded first so both fit on a 12 GB card.
- **ElevenLabs**: set `voice.elevenlabs.voice` to a name or id (`technews voices --engine elevenlabs`). Neighbouring scenes are sent along so the delivery flows across cuts, and takes are cached per job, so re-recording after an edit only pays for changed scenes.

Every clip is mastered the same way (EQ, gentle compression, -16 LUFS), and the pause after each scene follows its punctuation. Add words a voice gets wrong under `voice.pronunciations` (for example `Asus: ay-soos`), then test with `technews say "Asus launched a laptop"`.

## Posting

| Target | How | Setup |
|---|---|---|
| Export folder | mp4 plus a `.txt` with the YouTube title/description and TikTok caption | none. Point `publish.export_dir` at a OneDrive or Google Drive folder to get videos on your phone |
| Discord review | The finished video is posted to a channel, with anything the fact check flagged | a channel webhook in `DISCORD_WEBHOOK_URL` |
| YouTube Shorts | Data API v3 resumable upload | Google Cloud project with the YouTube Data API. Set the OAuth consent screen to **In production** (in Testing, tokens expire after 7 days). Save the Desktop OAuth client as `config/secrets/youtube_client_secret.json`, then run `technews auth youtube` |
| TikTok | Content Posting API, **inbox draft**: you tap post in the app | TikTok developer app with Login Kit and Content Posting API. Set `TIKTOK_CLIENT_KEY/SECRET/REDIRECT_URI` in `.env`, then run `technews auth tiktok` |

Turn targets on under `publish.targets` in `config/config.yaml`.

Platform limits:
- **YouTube:** uploads from an API project that hasn't passed Google's audit are locked to private. Keep `privacy: private` until your project is approved. You can apply through the audit form; small personal projects have reportedly been approved.
- **TikTok:** only audited apps can post publicly, and TikTok's guidelines don't approve tools for posting to your own accounts, so the video goes to your drafts inbox. You can also post the exported file by hand.
- **Never automate posting through a browser.** It breaks every platform's terms and risks bans.

## Running it every day

Windows Task Scheduler, every day at 9:00 (change the path if needed):

```bat
schtasks /Create /SC DAILY /ST 09:00 /TN "Tech News Shorts" /TR "cmd /c cd /d \"E:\Github\Tech News Shorts\" && uv run technews daily >> data\daily.log 2>&1"
```

`technews daily --dry-run` does everything except upload. If a run fails, a message is posted to the Discord webhook.

## How it works

```
RSS feeds + Hacker News -> cluster + rank (skip covered) -> article text (trafilatura)
  -> LLM script (JSON schema) -> repair + number check
  -> voice per scene: Kokoro / Chatterbox / ElevenLabs (word timings, mastering, mouth envelope) -> props.json
  -> Remotion (video/render.mjs) -> video.mp4 -> export / Discord / YouTube / TikTok
```

A job folder holds everything for one video:

```
out/2026-10-20_apple-touchscreen-macbook-pro/
  story.json  script.json  voice/s00.wav ... voice/timing.json  sfx/  props.json  video.mp4  metadata.json  job.json
```

## Changing the look

- Channel name, outro line and colours: the `brand` section of `config/config.yaml`.
- Background music: put tracks you have the rights to in `assets/music/`. One is picked per video, at a low volume.
- The video itself is React. `video/src/NewsShort.tsx` lays it out, `video/src/scenes/` has one file per graphic type, and `video/src/components/Mascot.tsx` is Byte. Run `npm run studio` in `video/` to see changes live.

## Accuracy, credit and rights

- Scripts may only use facts from the source article. Numbers in stat graphics are checked against it, and anything that looks invented is listed under "check before posting" in the terminal and on Discord. Review before you publish.
- Every description credits the source outlet and links the article, and says the narration is an AI voice. TikTok posts set the AI-generated label.
- YouTube doesn't monetize mass-produced, repetitive content. Your own review, picks and angle are what make the channel yours.
- Licenses: Remotion is free for individuals and companies of up to 3 people; larger companies need a [company license](https://www.remotion.pro). Kokoro model (Apache 2.0), kokoro-onnx (MIT), Chatterbox (MIT; its audio carries Resemble's inaudible Perth watermark), Barlow fonts (SIL OFL), Lucide icons (ISC).

## Development

```bash
uv run pytest                      # fast tests (offline)
RUN_SLOW=1 uv run pytest -m slow   # real voice + render (needs the model and npm install)
uv run ruff check src tests
cd video && npm run typecheck && npm run studio
```

## License

MIT
