"""Regressão curta de Time > Timesheets (listagem x detalhe), somente leitura.

Origem: relato do cliente de que o período, o status ou os lançamentos do
detalhe nem sempre correspondem ao item escolhido na listagem de timesheets
submetidos. Os testes comparam listagem, detalhe e histórico com a API e
cobrem as variações de navegação (reload, voltar, troca de período).

Nenhuma ação de aprovação/rejeição é executada: os botões não são acionados.
"""

from __future__ import annotations

import json

import allure
import pytest
from playwright.sync_api import Page, Route, expect

from orangehrm.api.core import CoreApi
from orangehrm.api.models import ListResponse, PendingTimesheet
from orangehrm.api.time import TimeApi
from orangehrm.config.settings import Settings
from orangehrm.pages.time.employee_timesheets_page import EmployeeTimesheetsPage
from orangehrm.pages.time.timesheet_detail_page import TimesheetDetailPage

pytestmark = [pytest.mark.ui, allure.feature("Time - Timesheets (listagem x detalhe)")]

MAX_ITEMS_TO_OPEN = 3


def employee_name(item: PendingTimesheet) -> str:
    emp = item.employee
    return " ".join(p for p in (emp.first_name, emp.middle_name, emp.last_name) if p)


def normalize(text: str) -> str:
    return " ".join(text.split())


def list_period(item: PendingTimesheet, core: CoreApi) -> str:
    return f"{core.format_date(item.start_date)} - {core.format_date(item.end_date)}"


def detail_period(item: PendingTimesheet, core: CoreApi) -> str:
    to = core.text("general.to").lower()
    return f"{core.format_date(item.start_date)} {to} {core.format_date(item.end_date)}"


@pytest.fixture(scope="module")
def time_api(admin_api) -> TimeApi:
    return TimeApi(admin_api)


@pytest.fixture(scope="module")
def pending(time_api: TimeApi) -> list[PendingTimesheet]:
    items = time_api.pending_timesheets(limit=50).data
    if not items:
        pytest.skip("Sem timesheets submetidos pendentes: massa ausente para comparar")
    return items


@pytest.mark.smoke
@allure.title("Listagem exibe exatamente os timesheets pendentes retornados pela API")
def test_list_matches_api(admin_page: Page, settings: Settings, core_api: CoreApi):
    listing = EmployeeTimesheetsPage(admin_page, settings)

    with admin_page.expect_response(EmployeeTimesheetsPage.LIST_API_GLOB) as info:
        listing.goto()
    api = ListResponse[PendingTimesheet].model_validate(info.value.json())
    if not api.data:
        expect(listing.table.rows).to_have_count(0)
        assert listing.table.records_found() == 0
        pytest.skip("Lista vazia: estado vazio validado; sem itens para comparar")

    assert listing.table.records_found() == api.meta.total
    ui_rows = [
        {k: normalize(v) for k, v in row.items() if k != "Actions"}
        for row in listing.table.row_values()
    ]
    api_rows = [
        {"Employee Name": employee_name(i), "Timesheet Period": list_period(i, core_api)}
        for i in api.data
    ]
    assert ui_rows == api_rows
    listing.attach_screenshot("Timesheets pendentes de ação")


@allure.title("Busca do detalhe (funcionário + data inicial) resolve o mesmo timesheet da listagem")
def test_detail_lookup_resolves_listed_timesheet(time_api: TimeApi, pending):
    mismatches = []
    for item in pending:
        found = time_api.timesheet_for_date(item.employee.emp_number or 0, item.start_date)
        if (found.id, found.start_date, found.end_date) != (
            item.id,
            item.start_date,
            item.end_date,
        ) or (found.status and item.status and found.status.id != item.status.id):
            mismatches.append(
                {
                    "listagem": item.model_dump(mode="json", by_alias=True),
                    "detalhe": found.model_dump(mode="json", by_alias=True),
                }
            )
    allure.attach(
        json.dumps(mismatches, indent=2, ensure_ascii=False),
        name="Divergências listagem x detalhe (API)",
        attachment_type=allure.attachment_type.JSON,
    )
    assert not mismatches, f"{len(mismatches)} timesheet(s) abrem outro registro no detalhe"


@pytest.mark.smoke
@allure.title("View abre o detalhe do item selecionado: período, status, lançamentos e histórico")
def test_view_opens_selected_timesheet(
    admin_page: Page, settings: Settings, core_api: CoreApi, time_api: TimeApi, pending
):
    for index, item in enumerate(pending[:MAX_ITEMS_TO_OPEN]):
        with allure.step(f"Item {index + 1}: {employee_name(item)} {item.start_date}"):
            listing = EmployeeTimesheetsPage(admin_page, settings)
            listing.goto()
            listing.view(index)
            detail = TimesheetDetailPage(admin_page, settings)
            detail.wait_until_loaded()

            entries = time_api.entries(item.id)
            logs = time_api.action_logs(item.id)

            expect(detail.title).to_contain_text(item.employee.first_name or "")
            expect(detail.period_input).to_have_value(detail_period(item, core_api))
            assert detail.status_text() == (item.status.name if item.status else None)
            if entries.data:
                expect(detail.entry_rows).to_have_count(len(entries.data))
                expect(detail.grand_total).to_have_text(entries.meta.sum.label)
            else:
                expect(detail.body_message).to_contain_text("No Records Found")
            assert len(detail.action_log_rows()) == len(logs)
            detail.attach_screenshot(f"Detalhe - {employee_name(item)} {item.start_date}")


@allure.title("Reload e voltar do navegador mantêm a correspondência com a listagem")
def test_reload_and_back(admin_page: Page, settings: Settings, core_api: CoreApi, pending):
    item = pending[0]
    listing = EmployeeTimesheetsPage(admin_page, settings)
    listing.goto()
    listing.view(0)
    detail = TimesheetDetailPage(admin_page, settings)
    detail.wait_until_loaded()
    expected = detail_period(item, core_api)

    with allure.step("Recarregar a página do detalhe"):
        admin_page.reload()
        detail.wait_until_loaded()
    expect(detail.period_input).to_have_value(expected)

    with allure.step("Voltar para a listagem e avançar de novo"):
        admin_page.go_back()
        listing.wait_until_loaded()
        expect(admin_page).to_have_url(listing.url_for())
        admin_page.go_forward()
        detail.wait_until_loaded()
    expect(detail.period_input).to_have_value(expected)


@allure.title("Período anterior e depois próximo volta ao mesmo timesheet")
def test_previous_then_next_returns_same_timesheet(
    admin_page: Page, settings: Settings, core_api: CoreApi, time_api: TimeApi, pending
):
    item = pending[0]
    detail = TimesheetDetailPage(admin_page, settings)
    detail.open(item.employee.emp_number or 0, item.start_date.isoformat())
    total_before = detail.grand_total.inner_text() if detail.grand_total.count() else None

    with admin_page.expect_response(TimesheetDetailPage.DEFAULT_API_GLOB):
        detail.go_previous()
    detail.wait_until_loaded()
    with admin_page.expect_response(TimesheetDetailPage.DEFAULT_API_GLOB):
        detail.go_next()
    detail.wait_until_loaded()

    expect(detail.period_input).to_have_value(detail_period(item, core_api))
    assert detail.status_text() == (item.status.name if item.status else None)
    if total_before is not None:
        expect(detail.grand_total).to_have_text(total_before)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG-TIME-01: respostas fora de ordem na troca de período sobrescrevem o "
        "detalhe (useTimesheet.loadTimesheet não descarta requisições antigas)"
    ),
)
@allure.title("Troca rápida de período com rede lenta não pode exibir outro período")
def test_fast_period_switch_with_slow_network(
    admin_page: Page, settings: Settings, core_api: CoreApi, pending
):
    """Simula rede lenta só para a semana anterior: o usuário clica em
    "anterior" e logo em "próximo"; a resposta atrasada chega por último."""
    item = pending[0]
    detail = TimesheetDetailPage(admin_page, settings)
    detail.open(item.employee.emp_number or 0, item.start_date.isoformat())
    expected = detail_period(item, core_api)
    held: list[Route] = []

    def hold_previous_week(route: Route) -> None:
        if f"date={item.start_date.isoformat()}" in route.request.url:
            route.continue_()
        else:
            held.append(route)

    admin_page.route(TimesheetDetailPage.DEFAULT_API_GLOB, hold_previous_week)
    detail.go_previous()
    with admin_page.expect_response(TimesheetDetailPage.DEFAULT_API_GLOB):
        detail.go_next()
    detail.wait_until_loaded()
    expect(detail.period_input).to_have_value(expected)

    with allure.step("Liberar a resposta atrasada da semana anterior"):
        for route in held:
            route.continue_()
        admin_page.wait_for_timeout(1_500)
    detail.attach_screenshot("Detalhe após resposta atrasada")

    assert detail.period_text() == expected, (
        f"Detalhe mudou para {detail.period_text()!r} embora a semana selecionada seja "
        f"{expected!r} (URL: {admin_page.url})"
    )
