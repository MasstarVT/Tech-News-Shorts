"""Environment self-check: ``technews doctor``."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

import httpx

from .config import AppConfig, load_config, secret
from .publish.base import client_secret_path, token_path

Status = Literal["ok", "warn", "fail"]
CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


@dataclass
class Check:
    name: str
    status: Status
    detail: str
    fix: str = ""


def _out(args: list[str], timeout: float = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, creationflags=CREATE_FLAGS,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def check_node(cfg: AppConfig) -> list[Check]:
    checks: list[Check] = []
    node = shutil.which("node")
    if not node:
        return [Check("Node.js", "fail", "not on PATH", "Install Node 20+ from https://nodejs.org")]
    _, out = _out([node, "--version"])
    ver = out.strip().lstrip("v")
    major = int(ver.split(".")[0]) if ver[:1].isdigit() else 0
    checks.append(Check("Node.js", "ok" if major >= 20 else "warn", f"v{ver}", "" if major >= 20 else "Use Node 20 or newer"))
    pkg = cfg.paths.video / "node_modules" / "@remotion" / "renderer" / "package.json"
    if pkg.exists():
        v = json.loads(pkg.read_text(encoding="utf-8")).get("version", "?")
        checks.append(Check("Remotion", "ok", f"v{v} installed in video/"))
    else:
        checks.append(Check("Remotion", "fail", "video/node_modules missing", f"cd \"{cfg.paths.video}\" && npm install"))
    return checks


def check_voice(cfg: AppConfig) -> list[Check]:
    from .voice.kokoro import model_paths

    checks: list[Check] = []
    model, voices = model_paths(cfg)
    have = model.exists() and voices.exists()
    checks.append(Check("Kokoro model", "ok" if have else "warn",
                        f"{model.name} + {voices.name}" if have else "not downloaded yet",
                        "" if have else "Downloads automatically on the first run (~350 MB), or run `technews voices`"))
    try:
        import espeakng_loader  # noqa: F401
        import kokoro_onnx  # noqa: F401

        checks.append(Check("kokoro-onnx", "ok", "installed (espeak-ng bundled)"))
    except ImportError as e:
        checks.append(Check("kokoro-onnx", "fail", str(e), "uv sync"))
    if cfg.voice.engine == "chatterbox":
        from .voice.chatterbox import venv_dir, venv_python

        have = venv_python(cfg).exists()
        checks.append(Check("Chatterbox", "ok" if have else "fail",
                            f"{cfg.voice.chatterbox.model} model, voice {cfg.voice.chatterbox.voice}" if have
                            else f"no venv at {venv_dir(cfg)}", "" if have else "technews setup-chatterbox"))
    elif cfg.voice.engine == "elevenlabs":
        env = cfg.voice.elevenlabs.api_key_env
        have = bool(secret(env))
        checks.append(Check("ElevenLabs", "ok" if have else "fail",
                            f"{cfg.voice.elevenlabs.model}, voice {cfg.voice.elevenlabs.voice}" if have else f"{env} missing",
                            "" if have else f"Add {env}=... to .env"))
    return checks


def check_llm(cfg: AppConfig) -> list[Check]:
    route = cfg.llm.tasks.get("script")
    if route is None or route.provider in ("null", "none", ""):
        return [Check("Script writer", "warn", "provider: null (template scripts, no AI)",
                      "Set llm.tasks.script in config/config.yaml")]
    if route.provider == "ollama":
        base = (cfg.llm.providers.get("ollama").base_url if cfg.llm.providers.get("ollama") else None) or "http://127.0.0.1:11434"
        try:
            models = [m["name"] for m in httpx.get(f"{base}/api/tags", timeout=3).json().get("models", [])]
        except Exception:
            return [Check("Script writer", "fail", f"Ollama not reachable at {base}", "Start Ollama (https://ollama.com)")]
        want = route.model if ":" in route.model else f"{route.model}:latest"
        if want in models or route.model in models:
            return [Check("Script writer", "ok", f"ollama:{route.model}")]
        return [Check("Script writer", "fail", f"ollama model {route.model} not pulled ({len(models)} installed)",
                      f"ollama pull {route.model}")]
    prov = cfg.llm.providers.get(route.provider)
    key_env = prov.api_key_env if prov else None
    ok = bool(secret(key_env)) if key_env else True
    return [Check("Script writer", "ok" if ok else "fail", f"{route.provider}:{route.model}",
                  "" if ok else f"Add {key_env}=... to .env and `uv sync --extra llm`")]


def check_publish(cfg: AppConfig) -> list[Check]:
    checks: list[Check] = []
    for t in cfg.publish.targets:
        if t.platform == "export":
            checks.append(Check("Export folder", "ok" if t.enabled else "warn", str(cfg.paths.resolve(cfg.publish.export_dir))))
            continue
        if not t.enabled:
            checks.append(Check({"youtube": "YouTube", "tiktok": "TikTok"}[t.platform], "ok", "disabled (enable in publish.targets)"))
            continue
        if t.platform == "youtube":
            if not client_secret_path("youtube").exists():
                checks.append(Check("YouTube", "fail", "no OAuth client", "Save it as config/secrets/youtube_client_secret.json"))
            elif not token_path("youtube", t.account).exists():
                checks.append(Check("YouTube", "fail", "not signed in", f"technews auth youtube --account {t.account}"))
            else:
                checks.append(Check("YouTube", "ok", f"account '{t.account}' connected, privacy {t.privacy}"))
            try:
                import googleapiclient  # noqa: F401
            except ImportError:
                checks.append(Check("YouTube client", "fail", "google-api-python-client missing", "uv sync --extra publish"))
        if t.platform == "tiktok":
            keys = all(secret(k) for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REDIRECT_URI"))
            if not keys:
                checks.append(Check("TikTok", "fail", "app keys missing", "Set TIKTOK_CLIENT_KEY/SECRET/REDIRECT_URI in .env"))
            elif not token_path("tiktok", t.account).exists():
                checks.append(Check("TikTok", "fail", "not signed in", f"technews auth tiktok --account {t.account}"))
            else:
                checks.append(Check("TikTok", "ok", f"account '{t.account}' connected ({t.mode})"))
    hook = secret(cfg.publish.discord_webhook_env)
    checks.append(Check("Discord webhook", "ok", "set" if hook else "not set (optional)",
                        "" if hook else f"Add {cfg.publish.discord_webhook_env}=... to .env to get videos on your phone"))
    return checks


def check_disk(cfg: AppConfig) -> Check:
    out = cfg.paths.output
    out.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(out).free / 1e9
    return Check("Disk space", "ok" if free_gb > 5 else "warn", f"{free_gb:,.0f} GB free at {out}")


def run_checks(cfg: AppConfig | None = None) -> list[Check]:
    cfg = cfg or load_config()
    checks = [Check("Python", "ok", sys.version.split()[0])]
    checks += check_node(cfg)
    checks += check_voice(cfg)
    checks += check_llm(cfg)
    checks += check_publish(cfg)
    checks.append(check_disk(cfg))
    return checks
