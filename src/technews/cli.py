"""Command-line interface: `technews --help`."""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from .config import CONFIG_DIR, PROJECT_ROOT, load_config

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Turn today's tech news into animated shorts.")
auth_app = typer.Typer(no_args_is_help=True, help="Connect YouTube / TikTok accounts.")
llm_app = typer.Typer(no_args_is_help=True, help="Inspect LLM providers.")
app.add_typer(auth_app, name="auth")
app.add_typer(llm_app, name="llm")

# Headlines are full of curly quotes and emoji; don't let a cp1252 console crash.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, ValueError):
        _stream.reconfigure(encoding="utf-8", errors="replace")
console = Console(legacy_windows=False)
log = logging.getLogger("technews")


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler(console=console, show_path=False, rich_tracebacks=True)],
    )
    for noisy in ("httpx", "httpcore", "urllib3", "googleapiclient", "trafilatura", "phonemizer", "kokoro_onnx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _fail(msg: str) -> None:
    console.print(f"[red]{msg}[/]")
    raise typer.Exit(1)


def _job(ref: str):
    from .jobs import Job

    try:
        return Job.open(load_config(), ref)
    except FileNotFoundError as e:
        _fail(str(e))


class _UI:
    """One progress line that follows the pipeline through its stages."""

    def __init__(self) -> None:
        self.progress = Progress(TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), TimeElapsedColumn(),
                                 console=console, transient=False)
        self.task = None

    def __enter__(self):
        self.progress.start()
        return self

    def __exit__(self, *exc):
        self.progress.stop()

    def stage(self, name: str) -> None:
        if self.task is not None:
            self.progress.update(self.task, completed=100)
        self.task = self.progress.add_task(name[:70], total=100)

    def voice(self, done: int, total: int) -> None:
        self.progress.update(self.task, completed=done / total * 100)

    def download(self, name: str, done: int, total: int) -> None:
        if total:
            self.progress.update(self.task, description=f"Downloading {name}", completed=done / total * 100)

    def render(self, stage: str, frac: float) -> None:
        label = {"bundle": "Bundling the video", "render": "Rendering the video",
                 "browser-download": "Downloading the renderer's browser"}.get(stage, stage)
        self.progress.update(self.task, description=label, completed=frac * 100)

    def hooks(self):
        from .pipeline import Hooks

        return Hooks(stage=self.stage, voice_progress=self.voice, download_progress=self.download,
                     render_progress=self.render)


def _print_script(job) -> None:
    script = job.load_script()
    table = Table(show_header=True, header_style="bold", title=script.title, title_justify="left")
    table.add_column("#", justify="right")
    table.add_column("Visual")
    table.add_column("Narration", overflow="fold")
    for i, s in enumerate(script.scenes, 1):
        v = s.visual
        shown = v.text or v.value or (f"{v.left} vs {v.right}" if v.type == "versus" else ", ".join(v.items))
        table.add_row(str(i), f"{v.type}: {shown}", s.narration)
    console.print(table)
    console.print(f"{script.word_count} words, written by {script.llm}")
    for w in script.warnings:
        console.print(f"[yellow]check:[/] {w}")


def _done(job) -> None:
    console.print(f"\n[green]Done:[/] {job.video_path if job.video_path.exists() else job.dir}")
    script = job.load_script()
    if script.warnings:
        console.print("[yellow]Check these before posting:[/]")
        for w in script.warnings:
            console.print(f"  - {w}")


# --------------------------------------------------------------------------- setup


@app.command("init")
def init_project(skip_npm: bool = typer.Option(False, help="Don't run npm install in video/")) -> None:
    """Create config/config.yaml and .env from the examples, and install the video renderer."""
    pairs = [(CONFIG_DIR / "config.example.yaml", CONFIG_DIR / "config.yaml"), (PROJECT_ROOT / ".env.example", PROJECT_ROOT / ".env")]
    for src, dst in pairs:
        if dst.exists():
            console.print(f"[yellow]exists[/] {dst}")
        elif src.exists():
            shutil.copyfile(src, dst)
            console.print(f"[green]created[/] {dst}")
    load_config.cache_clear()
    video = load_config().paths.video
    if not skip_npm and not (video / "node_modules").exists():
        npm = shutil.which("npm")
        if not npm:
            _fail("npm not found - install Node 20+ from https://nodejs.org, then run `technews init` again")
        console.print("Installing the video renderer (npm install)...")
        code = subprocess.call([npm, "install", "--no-audit", "--no-fund"], cwd=video, shell=sys.platform == "win32")
        if code != 0:
            _fail("npm install failed")
    console.print("Next: `uv run technews doctor`")


@app.command()
def doctor() -> None:
    """Check Node/Remotion, the voice model, the script writer and publishing setup."""
    from .doctor import run_checks

    checks = run_checks()
    table = Table(show_header=True, header_style="bold")
    for col in ("Check", "Status", "Detail", "Fix"):
        table.add_column(col, overflow="fold")
    colors = {"ok": "green", "warn": "yellow", "fail": "red"}
    for c in checks:
        table.add_row(c.name, f"[{colors[c.status]}]{c.status}[/]", c.detail, c.fix)
    console.print(table)
    fails = sum(c.status == "fail" for c in checks)
    console.print(f"{fails} failing, {sum(c.status == 'warn' for c in checks)} warnings")
    raise typer.Exit(1 if fails else 0)


# --------------------------------------------------------------------------- pipeline


@app.command("news")
def list_news(limit: int = typer.Option(15, help="How many to show")) -> None:
    """Show today's ranked candidate stories (pick one with `technews make --pick N`)."""
    from . import news

    cfg = load_config()
    with console.status("Fetching feeds..."):
        ranked = news.candidates(cfg)
    if not ranked:
        _fail("No fresh stories found")
    table = Table(show_header=True, header_style="bold")
    for col in ("#", "Score", "Source", "Age", "Title"):
        table.add_column(col, overflow="fold")
    now = datetime.now().astimezone()
    for i, s in enumerate(ranked[:limit], 1):
        age = f"{(now - s.published).total_seconds() / 3600:.0f}h" if s.published else "?"
        extra = f" [dim](+{len(s.also_in)} outlets)[/]" if s.also_in else ""
        hn = f" [dim]HN {s.points}[/]" if s.points else ""
        table.add_row(str(i), f"{s.score:.2f}", s.source, age, f"{s.title}{extra}{hn}")
    console.print(table)


@app.command()
def make(
    pick: int = typer.Option(None, help="Use the Nth story from `technews news` instead of the top one"),
    url: str = typer.Option(None, help="Make a video about this article instead"),
    llm: str = typer.Option(None, help="Script writer override: provider or provider:model (e.g. ollama:qwen3:14b, null)"),
    voice: str = typer.Option(None, help="Kokoro voice (see `technews voices`)"),
    render: bool = typer.Option(True, help="Render the video (--no-render stops after the voice)"),
    publish: bool = typer.Option(False, help="Publish to the enabled targets when done"),
    to: str = typer.Option(None, help="Comma-separated targets for --publish (export,youtube,tiktok)"),
    dry_run: bool = typer.Option(False, help="With --publish: record what would be posted, upload nothing"),
) -> None:
    """Make one video: pick a story, write the script, record the voice, render."""
    from .pipeline import NoStories
    from .pipeline import make as run

    cfg = load_config()
    only = [t.strip() for t in to.split(",")] if to else None
    try:
        with _UI() as ui:
            job = run(cfg, pick=pick, url=url, llm=llm, voice=voice, render=render, publish=publish or bool(to),
                      only=only, dry_run=dry_run, hooks=ui.hooks())
    except NoStories as e:
        _fail(str(e))
    _print_script(job)
    _done(job)


@app.command()
def script(job_ref: str = typer.Argument("latest"), llm: str = typer.Option(None, help="provider or provider:model")) -> None:
    """Rewrite a job's script (then run `voice` and `render` again)."""
    from .pipeline import stage_script

    job = _job(job_ref)
    with console.status("Writing the script..."):
        stage_script(job, load_config(), llm)
    _print_script(job)


@app.command("voice")
def voice_cmd(
    job_ref: str = typer.Argument("latest"),
    voice: str = typer.Option(None, help="Kokoro voice"),
    speed: float = typer.Option(None, help="Speaking speed, 0.5-2.0"),
) -> None:
    """Record (or re-record) a job's narration from script.json."""
    from .pipeline import stage_voice

    job = _job(job_ref)
    with _UI() as ui:
        ui.stage("Recording the voice")
        stage_voice(job, load_config(), voice, speed, hooks=ui.hooks())
    console.print(f"[green]Voice saved[/] in {job.voice_dir}")


@app.command("render")
def render_cmd(job_ref: str = typer.Argument("latest")) -> None:
    """Render a job's video from its script and voice."""
    from .pipeline import stage_render

    job = _job(job_ref)
    with _UI() as ui:
        ui.stage("Rendering the video")
        stage_render(job, load_config(), ui.hooks())
    _done(job)


@app.command()
def still(job_ref: str = typer.Argument("latest"), frames: str = typer.Option("45", help="Frame or comma list, e.g. 45,200")) -> None:
    """Render single frames of a job to PNG for a quick look."""
    from .render import render_still

    job = _job(job_ref)
    with console.status("Rendering..."):
        out = render_still(job, load_config(), frames)
    console.print(f"[green]Saved[/] {out}")


@app.command()
def preview(job_ref: str = typer.Argument("latest")) -> None:
    """Open a job in Remotion Studio (live preview in the browser)."""
    from .render import build_props, check_setup

    cfg = load_config()
    job = _job(job_ref)
    check_setup(cfg)
    build_props(job, cfg)
    npx = shutil.which("npx")
    if not npx:
        _fail("npx not found - install Node 20+")
    args = [npx, "remotion", "studio", "src/index.ts", f"--props={job.props_path}", f"--public-dir={job.dir}"]
    subprocess.call(args, cwd=cfg.paths.video, shell=sys.platform == "win32")


@app.command("publish")
def publish_cmd(
    job_ref: str = typer.Argument("latest"),
    to: str = typer.Option(None, help="Comma-separated targets (default: the enabled ones in config)"),
    dry_run: bool = typer.Option(False, help="Record what would be posted, upload nothing"),
) -> None:
    """Publish a rendered job (export folder, YouTube, TikTok inbox)."""
    from .publish import PublishError, notify, publish_job

    cfg = load_config()
    job = _job(job_ref)
    only = [t.strip() for t in to.split(",")] if to else None
    try:
        with console.status("Publishing..."):
            results = publish_job(job, cfg, only=only, dry_run=dry_run)
    except PublishError as e:
        _fail(str(e))
    for platform, res in results.items():
        color = "green" if res["status"] in ("published", "needs_action", "dry_run") else "red"
        detail = res.get("url") or res.get("path") or res.get("error", "")
        note = " (open TikTok to finish the post)" if res["status"] == "needs_action" else ""
        console.print(f"[{color}]{platform}: {res['status']}[/] {detail}{note}")
    if not dry_run:
        notify(job, cfg, results)


@app.command()
def daily(dry_run: bool = typer.Option(False, help="Do everything except uploading")) -> None:
    """Scheduled entry point: make today's video and publish it to the enabled targets."""
    from .pipeline import make as run

    cfg = load_config()
    try:
        job = run(cfg, render=True, publish=True, dry_run=dry_run)
    except Exception as e:
        log.exception("Daily run failed")
        _notify_failure(cfg, e)
        raise typer.Exit(1) from e
    _done(job)


def _notify_failure(cfg, err: Exception) -> None:
    import httpx

    from .config import secret

    url = secret(cfg.publish.discord_webhook_env)
    if url:
        with contextlib.suppress(httpx.HTTPError):
            httpx.post(url, json={"content": f"Tech News Shorts daily run failed: {str(err)[:1500]}"}, timeout=20)


@app.command("jobs")
def list_jobs(limit: int = typer.Option(10)) -> None:
    """List recent jobs and where they got to."""
    from .jobs import Job

    cfg = load_config()
    folders = sorted(cfg.paths.output.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    table = Table(show_header=True, header_style="bold")
    for col in ("Job", "Status", "Published"):
        table.add_column(col, overflow="fold")
    for f in folders:
        state = Job(f.parent, cfg).load_state()
        pub = ", ".join(f"{k}:{v.get('status')}" for k, v in state.published.items())
        table.add_row(state.id, state.status, pub)
    console.print(table)


# --------------------------------------------------------------------------- voice tools


@app.command()
def voices() -> None:
    """List the Kokoro voices (downloads the model on first use)."""
    from .voice.kokoro import KokoroEngine

    cfg = load_config()
    with console.status("Loading Kokoro..."):
        engine = KokoroEngine(cfg)
    names = engine.voices()
    console.print(", ".join(names))
    console.print(f"\nCurrent: [bold]{cfg.voice.voice}[/] at speed {cfg.voice.speed}. Best English voices: "
                  "af_heart, af_bella (US female), am_michael, am_fenrir, am_puck (US male), bf_emma, bm_george (UK).")


@app.command()
def say(
    text: str,
    voice: str = typer.Option(None),
    speed: float = typer.Option(None),
    out: Path = typer.Option(Path("data/say.wav"), help="Where to write the audio"),
) -> None:
    """Speak a line with Kokoro to audition voices and pronunciations."""
    import soundfile as sf

    from .voice.kokoro import KokoroEngine
    from .voice.speech import spoken_text, to_speech

    cfg = load_config()
    engine = KokoroEngine(cfg)
    spoken = spoken_text(to_speech(text, cfg.voice.pronunciations))
    audio, sr, _ = engine.synth(spoken, voice or cfg.voice.voice, speed or cfg.voice.speed)
    target = out if out.is_absolute() else PROJECT_ROOT / out
    target.parent.mkdir(parents=True, exist_ok=True)
    sf.write(target, audio, sr)
    console.print(f"Read as: {spoken}\n[green]Saved[/] {target}")


# --------------------------------------------------------------------------- accounts


@auth_app.command("youtube")
def auth_youtube(account: str = typer.Option("main", help="Name for this account in config")) -> None:
    """Sign in to YouTube in the browser (needs config/secrets/youtube_client_secret.json)."""
    from .publish.base import PublishError
    from .publish.youtube import authorize

    try:
        info = authorize(account)
    except PublishError as e:
        _fail(str(e))
    console.print(f"[green]Connected[/] {info.get('title', '?')} as '{account}'")


@auth_app.command("tiktok")
def auth_tiktok(account: str = typer.Option("main")) -> None:
    """Sign in to TikTok: open the link, approve, then paste the URL you were redirected to."""
    from .publish.base import PublishError
    from .publish.tiktok import authorize_url, authorize_with_redirect

    state: dict = {}
    try:
        console.print(f"Open this link and approve access:\n{authorize_url(state)}\n")
        redirected = typer.prompt("Paste the full URL you were redirected to")
        data = authorize_with_redirect(account, redirected, state)
    except PublishError as e:
        _fail(str(e))
    console.print(f"[green]Connected[/] {data.get('display_name') or data.get('open_id')} as '{account}'")


@llm_app.command("models")
def llm_models(provider: str) -> None:
    """List the models a provider offers (e.g. `technews llm models ollama`)."""
    from .llm import LLMError, get_provider

    try:
        names = get_provider(provider).list_models()
    except LLMError as e:
        _fail(str(e))
    console.print("\n".join(names) or "(none)")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    app()
