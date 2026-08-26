import re
from pathlib import Path

RUNBOOK = Path("docs/production-installation-runbook.md")


def _text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def test_every_runbook_phase_and_step_has_beginner_execution_context() -> None:
    text = _text()
    assert [int(value) for value in re.findall(r"^## Phase (\d+)", text, re.MULTILINE)] == list(
        range(17)
    )
    steps = list(re.finditer(r"^### Step ([^\n]+)", text, re.MULTILINE))
    assert len(steps) >= 50
    for index, step in enumerate(steps):
        end = steps[index + 1].start() if index + 1 < len(steps) else len(text)
        assert "**Where:**" in text[step.end() : end], step.group(1)
    for phase in range(17):
        start = text.index(f"## Phase {phase} ")
        end_marker = f"## Phase {phase + 1} "
        end = text.index(end_marker) if phase < 16 else len(text)
        assert f"**PASS gate {phase}:**" in text[start:end]


def test_runbook_uses_supported_private_deployment_and_safe_paths() -> None:
    text = _text()
    console_blocks = "\n".join(re.findall(r"```console\n(.*?)```", text, re.DOTALL))
    assert "commissioning-init" in console_blocks
    assert "commissioning-check --stage workstation" in console_blocks
    assert "commissioning-check --stage deployment" in console_blocks
    assert "hosting-deploy --target truenas-api" in console_blocks
    assert "--api-key-file /mnt/apps/secrets/truenas-deployer-api-token" in console_blocks
    assert "/mnt/app-recovery/hosting-revisions/pnas-state" in text
    assert "/mnt/apps/pnas/state" not in text
    assert "docker compose" not in console_blocks
    assert "docker network create" not in console_blocks
    assert text.count("```") % 2 == 0


def test_staging_and_production_tls_instructions_are_distinct() -> None:
    text = _text()
    staging = text[text.index("## Phase 13 ") : text.index("## Phase 14 ")]
    production = text[text.index("## Phase 14 ") : text.index("## Phase 15 ")]
    assert "curl --insecure" in staging
    assert "curl --insecure" not in production
    assert "Do not use `--insecure`" in production
    assert "rm /mnt/apps/secrets/truenas-deployer-api-token" in production
