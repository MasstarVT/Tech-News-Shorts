from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from technews.config import AppConfig
from technews.models import Story

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def cfg(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "paths": {"data_dir": str(tmp_path / "data"), "output_dir": str(tmp_path / "out")},
            "publish": {"export_dir": str(tmp_path / "exports")},
            "render": {"music_dir": str(tmp_path / "music")},
        }
    )


@pytest.fixture
def story() -> Story:
    return Story(
        id="abc123",
        title="Chipmaker unveils faster laptop processor, claims 30% gain",
        url="https://example.org/b/chip",
        source="Sample Feed B",
        published=datetime(2026, 10, 20, 7, 30, tzinfo=UTC),
        summary="Short teaser.",
        text=(
            "The company announced a laptop processor it says is 30% faster than the previous generation. "
            "It ships in November and costs $499 for laptop makers. The chip uses a 3 nanometer process. "
            "Analysts expect the first laptops to arrive in time for the holidays. The company did not share "
            "battery life numbers."
        ),
    )
