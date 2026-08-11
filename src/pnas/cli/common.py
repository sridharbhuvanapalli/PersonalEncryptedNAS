from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from pnas.config import PNASConfig, load_config
from pnas.mock import MockTrueNASAdapter

console = Console()


def context_config(ctx: typer.Context) -> PNASConfig:
    return load_config(ctx.obj["config_path"])


def mock_adapter(ctx: typer.Context) -> MockTrueNASAdapter:
    config = context_config(ctx)
    if config.truenas.adapter != "mock":
        raise typer.BadParameter("this command path currently requires adapter: mock")
    return MockTrueNASAdapter(ctx.obj["fixture_path"])


def emit_json(value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    console.print_json(json.dumps(value, default=str))


def existing_path(value: str) -> Path:
    path = Path(value)
    if not path.exists():
        raise typer.BadParameter(f"path does not exist: {path}")
    return path
