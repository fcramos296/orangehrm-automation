"""Coleta de informações do ambiente para o relatório Allure.

O desafio pede registrar data, versão exibida e diferenças do ambiente; o
``environment.properties`` do Allure carrega isso em toda execução.
"""

from __future__ import annotations

import platform
import re
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from playwright.sync_api import APIRequestContext

from orangehrm.config.settings import Settings

_VERSION_RE = re.compile(r"OrangeHRM OS ([\d.]+)")


def detect_app_version(request: APIRequestContext, settings: Settings) -> str:
    try:
        html = request.get(f"{settings.app_url}/auth/login").text()
    except Exception as exc:  # noqa: BLE001 - informativo, nunca deve derrubar a suíte
        return f"indisponível ({type(exc).__name__})"
    match = _VERSION_RE.search(html)
    return match.group(1) if match else "não identificada"


def _pkg(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "n/a"


def write_allure_environment(
    alluredir: Path, settings: Settings, app_version: str, browser: str
) -> None:
    alluredir.mkdir(parents=True, exist_ok=True)
    props = {
        "Base.URL": str(settings.base_url),
        "OrangeHRM.Version": app_version,
        "Shared.Environment": str(settings.is_shared_environment).lower(),
        "Write.Scenarios": "enabled" if settings.allow_write else "disabled",
        "Browser": browser,
        "Playwright": _pkg("playwright"),
        "Python": platform.python_version(),
        "OS": f"{platform.system()} {platform.release()}",
        "Executed.At.UTC": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
    }
    lines = [f"{k}={v}" for k, v in props.items()]
    (alluredir / "environment.properties").write_text("\n".join(lines) + "\n", encoding="utf-8")
