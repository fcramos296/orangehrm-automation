"""Fixtures compartilhadas.

Estratégia de autenticação "API first": o login é feito uma única vez por
sessão via HTTP, o ``storage_state`` resultante é injetado nos contextos de
navegador e os testes de UI começam direto na tela que validam.
"""

from __future__ import annotations

import contextlib
import json
import shutil
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import allure
import pytest
from playwright.sync_api import APIRequestContext, BrowserContext, Page, Playwright

from orangehrm.api.client import ApiClient
from orangehrm.api.recruitment import PublicRecruitmentApi, RecruitmentApi
from orangehrm.config.settings import Settings, get_settings
from orangehrm.support.environment import detect_app_version, write_allure_environment

CATEGORIES_FILE = Path(__file__).parent.parent / "allure" / "categories.json"


# --- configuração ------------------------------------------------------------


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def base_url(settings: Settings) -> str:
    """Sobrescreve o fixture do pytest-base-url com a URL do Settings."""
    return settings.app_url


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any], settings: Settings) -> dict:
    return {
        **browser_context_args,
        "locale": settings.locale,
        "timezone_id": settings.timezone_id,
        "viewport": {"width": 1366, "height": 900},
    }


@pytest.fixture(autouse=True)
def _default_timeouts(request: pytest.FixtureRequest, settings: Settings) -> None:
    if "page" in request.fixturenames:
        page: Page = request.getfixturevalue("page")
        page.set_default_timeout(settings.default_timeout_ms)
        page.set_default_navigation_timeout(settings.navigation_timeout_ms)


@pytest.fixture(autouse=True)
def _skip_write_scenarios(request: pytest.FixtureRequest, settings: Settings) -> None:
    if request.node.get_closest_marker("write") and not settings.allow_write:
        pytest.skip(
            "Cenário grava dados: requer ambiente isolado com ORANGEHRM_ALLOW_WRITE=true "
            f"(ambiente atual: {settings.host})"
        )


# --- API ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def anonymous_request(
    playwright: Playwright, settings: Settings
) -> Generator[APIRequestContext, None, None]:
    ctx = playwright.request.new_context(timeout=settings.api_timeout_ms)
    yield ctx
    ctx.dispose()


@pytest.fixture(scope="session")
def admin_request(
    playwright: Playwright, settings: Settings
) -> Generator[APIRequestContext, None, None]:
    ctx = playwright.request.new_context(timeout=settings.api_timeout_ms)
    ApiClient(ctx, settings).login(
        settings.admin_username, settings.admin_password.get_secret_value()
    )
    yield ctx
    ctx.dispose()


@pytest.fixture(scope="session")
def public_api(anonymous_request: APIRequestContext, settings: Settings) -> PublicRecruitmentApi:
    return PublicRecruitmentApi(ApiClient(anonymous_request, settings))


@pytest.fixture(scope="session")
def anonymous_api(anonymous_request: APIRequestContext, settings: Settings) -> ApiClient:
    return ApiClient(anonymous_request, settings)


@pytest.fixture(scope="session")
def admin_api(admin_request: APIRequestContext, settings: Settings) -> ApiClient:
    return ApiClient(admin_request, settings)


@pytest.fixture(scope="session")
def recruitment_api(admin_api: ApiClient) -> RecruitmentApi:
    return RecruitmentApi(admin_api)


@pytest.fixture(scope="session")
def admin_storage_state(
    admin_request: APIRequestContext, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    path = tmp_path_factory.mktemp("auth") / "admin.json"
    admin_request.storage_state(path=path)
    return path


# --- UI ----------------------------------------------------------------------


@pytest.fixture
def admin_page(
    new_context: Callable[..., BrowserContext], admin_storage_state: Path, settings: Settings
) -> Page:
    """Página já autenticada como admin (sessão criada via API)."""
    context = new_context(storage_state=admin_storage_state)
    page = context.new_page()
    page.set_default_timeout(settings.default_timeout_ms)
    page.set_default_navigation_timeout(settings.navigation_timeout_ms)
    return page


# --- relatório ---------------------------------------------------------------


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator:
    outcome = yield
    report: pytest.TestReport = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    funcargs = getattr(item, "funcargs", {})
    for name in ("page", "admin_page"):
        page = funcargs.get(name)
        if isinstance(page, Page) and not page.is_closed():
            # Evidência é best-effort: falhar ao capturar não pode mascarar o erro real.
            with contextlib.suppress(Exception):
                allure.attach(
                    page.screenshot(full_page=True),
                    name=f"falha - {name} - {page.url}",
                    attachment_type=allure.attachment_type.PNG,
                )


@pytest.fixture(scope="session", autouse=True)
def _allure_environment(
    request: pytest.FixtureRequest, anonymous_request: APIRequestContext, settings: Settings
) -> None:
    alluredir = request.config.getoption("--alluredir", default=None)
    if not alluredir:
        return
    target = Path(alluredir)
    browsers = request.config.getoption("--browser", default=None) or ["chromium"]
    write_allure_environment(
        target,
        settings,
        app_version=detect_app_version(anonymous_request, settings),
        browser=",".join(browsers),
    )
    if CATEGORIES_FILE.exists():
        shutil.copy(CATEGORIES_FILE, target / "categories.json")


def pytest_report_header(config: pytest.Config) -> list[str]:
    try:
        s = get_settings()
    except Exception as exc:  # noqa: BLE001
        return [f"orangehrm: configuração inválida: {exc}"]
    return [
        f"orangehrm: base_url={s.base_url} allow_write={s.allow_write} "
        f"shared={s.is_shared_environment}",
        f"orangehrm: settings={json.dumps({'locale': s.locale, 'tz': s.timezone_id})}",
    ]
