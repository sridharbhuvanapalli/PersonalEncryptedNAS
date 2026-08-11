from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from pnas.audit import AuditLog
from pnas.cli.common import console, context_config, emit_json, existing_path, mock_adapter
from pnas.planning.capacity import calculate_raidz2_capacity
from pnas.planning.execution import (
    create_storage_plan,
    load_plan,
    required_confirmation,
    save_plan,
    validate_plan_for_apply,
    verify_confirmation,
)

app = typer.Typer(no_args_is_help=True, help="Safety-first TrueNAS bootstrap installer.")


@app.callback()
def main(
    ctx: typer.Context,
    config: str = typer.Option("config/pnas.example.yaml", help="Validated YAML configuration."),
    fixture: str = typer.Option(
        "tests/fixtures/inventory-four-4tb.json", help="Mock inventory fixture."
    ),
    state_dir: Path = typer.Option(Path("var"), help="Local plan and audit state."),
) -> None:
    ctx.obj = {
        "config_path": existing_path(config),
        "fixture_path": existing_path(fixture),
        "state_dir": state_dir,
    }


async def _inventory(ctx: typer.Context):  # type: ignore[no-untyped-def]
    return await mock_adapter(ctx).inventory()


@app.command()
def preflight(ctx: typer.Context) -> None:
    config = context_config(ctx)
    inventory = asyncio.run(_inventory(ctx))
    result = {
        "ok": inventory.aes_supported
        and inventory.memory_bytes >= 16 * 1024**3
        and inventory.ups_connected,
        "adapter": config.truenas.adapter,
        "dry_run": True,
        "api_version": inventory.api_version,
        "checks": {
            "aes": inventory.aes_supported,
            "memory_minimum": inventory.memory_bytes >= 16 * 1024**3,
            "ups": inventory.ups_connected,
        },
    }
    emit_json(result)
    if not result["ok"]:
        raise typer.Exit(2)


@app.command("inventory")
def inventory_command(ctx: typer.Context) -> None:
    emit_json(asyncio.run(_inventory(ctx)))


@app.command("capacity-plan")
def capacity_plan(ctx: typer.Context) -> None:
    inventory = asyncio.run(_inventory(ctx))
    drives = [drive for drive in inventory.drives if drive.role == "data"]
    if len(drives) not in (4, 8) or len({drive.capacity_bytes for drive in drives}) != 1:
        raise typer.BadParameter("capacity plan requires four or eight equal-capacity data drives")
    emit_json(
        calculate_raidz2_capacity(
            drive_count=len(drives), drive_capacity_bytes=drives[0].capacity_bytes
        )
    )


def _create_plan(ctx: typer.Context, action: str, serials: list[str], output: Path) -> None:
    plan = create_storage_plan(
        action=action,
        inventory=asyncio.run(_inventory(ctx)),
        storage=context_config(ctx).storage,
        selected_serials=tuple(serials),
    )
    save_plan(plan, output)
    AuditLog(ctx.obj["state_dir"] / "audit.jsonl").append(
        "storage.plan.created",
        actor="local-admin",
        outcome="success",
        details={"plan_id": plan.plan_id, "action": action, "serials": serials},
    )
    emit_json(plan)
    console.print(f"Required confirmation: {required_confirmation(plan)}")


@app.command("phase1-plan")
def phase1_plan(
    ctx: typer.Context,
    serial: list[str] = typer.Option(..., "--serial", help="Repeat for each selected drive."),
    output: Path = typer.Option(Path("var/phase1-plan.json")),
) -> None:
    _create_plan(ctx, "phase1-create", serial, output)


@app.command("expansion-preflight")
def expansion_preflight(ctx: typer.Context) -> None:
    inventory = asyncio.run(_inventory(ctx))
    emit_json(
        {
            "pool_healthy": inventory.pool_healthy,
            "scrub_succeeded": inventory.scrub_succeeded,
            "resilver_active": inventory.resilver_active,
            "ups_connected": inventory.ups_connected,
        }
    )


@app.command("expansion-plan")
def expansion_plan(
    ctx: typer.Context,
    serial: list[str] = typer.Option(..., "--serial"),
    output: Path = typer.Option(Path("var/phase2-plan.json")),
) -> None:
    _create_plan(ctx, "phase2-expand", serial, output)


def _apply_plan(
    ctx: typer.Context, plan_path: Path, confirmation: str, *, execute: bool, action: str
) -> None:
    plan = load_plan(plan_path)
    if plan.action != action:
        raise typer.BadParameter(f"plan action is {plan.action}, expected {action}")
    inventory = asyncio.run(_inventory(ctx))
    validate_plan_for_apply(plan, inventory)
    verify_confirmation(plan, confirmation)
    if not execute:
        console.print("Dry-run complete. No TrueNAS mutation was sent.")
        return
    if context_config(ctx).truenas.adapter == "mock":
        raise typer.BadParameter("destructive execution is disabled for the mock adapter")
    raise typer.BadParameter(
        "real destructive execution remains disabled until live hardware preflight is implemented"
    )


@app.command("phase1-apply")
def phase1_apply(
    ctx: typer.Context,
    plan: Path = typer.Option(..., exists=True),
    confirmation: str = typer.Option(..., prompt=True, hide_input=False),
    execute: bool = typer.Option(False, help="Request actual execution; dry-run otherwise."),
) -> None:
    _apply_plan(ctx, plan, confirmation, execute=execute, action="phase1-create")


@app.command("phase2-apply")
def phase2_apply(
    ctx: typer.Context,
    plan: Path = typer.Option(..., exists=True),
    confirmation: str = typer.Option(..., prompt=True, hide_input=False),
    execute: bool = typer.Option(False),
) -> None:
    _apply_plan(ctx, plan, confirmation, execute=execute, action="phase2-expand")


@app.command()
def resume(ctx: typer.Context) -> None:
    state_dir: Path = ctx.obj["state_dir"]
    plans = sorted(state_dir.glob("*-plan.json")) if state_dir.exists() else []
    emit_json({"resumable_plans": [str(path) for path in plans], "mutation_resumed": False})


@app.command()
def status(ctx: typer.Context) -> None:
    inventory = asyncio.run(_inventory(ctx))
    emit_json(
        {
            "truenas_version": inventory.truenas_version,
            "api_version": inventory.api_version,
            "pool_healthy": inventory.pool_healthy,
            "drive_count": len(inventory.drives),
            "dry_run_default": True,
        }
    )


if __name__ == "__main__":
    app()
