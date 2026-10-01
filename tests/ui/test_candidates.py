"""Consulta interna em Recruitment > Candidates (somente leitura).

A tela deve mostrar exatamente o que a API devolve: é o elo entre a
candidatura pública e o acompanhamento interno do recrutamento.
"""

from __future__ import annotations

import json

import allure
import pytest
from playwright.sync_api import Page, expect

from orangehrm.api.core import CoreApi
from orangehrm.api.models import CandidateSummary, ListResponse
from orangehrm.api.recruitment import RecruitmentApi
from orangehrm.config.settings import Settings
from orangehrm.data.applicants import SUITE_LAST_NAME_PREFIX
from orangehrm.pages.recruitment.candidates_page import CandidatesPage

pytestmark = [pytest.mark.ui, allure.feature("Recruitment - Consulta de candidatos")]

COLUMNS = ["Vacancy", "Candidate", "Hiring Manager", "Date of Application", "Status", "Actions"]


def expected_row(candidate: CandidateSummary, core: CoreApi) -> dict[str, str]:
    """Linha esperada na tela, aplicando as mesmas regras de exibição do front-end
    (ViewCandidatesList.vue): vaga fechada ganha "(Closed)", gerente removido vira
    "(Deleted)", ex-funcionário ganha "(Past Employee)" e a data segue o formato
    configurado em Admin > Localization."""
    vacancy = candidate.vacancy
    vacancy_name = ""
    if vacancy:
        closed = core.text("general.closed")
        vacancy_name = vacancy.name if vacancy.status else f"{vacancy.name} ({closed})"

    manager = vacancy.hiring_manager if vacancy else None
    if not manager or not manager.id:
        manager_name = core.text("general.deleted")
    elif manager.first_name == "Purged" and manager.last_name == "Employee":
        manager_name = core.text("general.purged_employee")
    else:
        manager_name = manager.full_name
        if manager.termination_id:
            manager_name = f"{manager_name} {core.text('general.past_employee')}"

    return {
        "Vacancy": vacancy_name,
        "Candidate": candidate.full_name,
        "Hiring Manager": manager_name,
        "Date of Application": (
            core.format_date(candidate.date_of_application) if candidate.date_of_application else ""
        ),
        "Status": candidate.status.label if candidate.status else "",
    }


def comparable(row: dict[str, str]) -> dict[str, str]:
    return {k: " ".join(v.split()) for k, v in row.items() if k != "Actions"}


@pytest.mark.smoke
@allure.title("Lista de candidatos renderiza exatamente os registros retornados pela API")
def test_candidate_list_matches_api_response(
    admin_page: Page, settings: Settings, core_api: CoreApi
):
    candidates = CandidatesPage(admin_page, settings)

    # Captura a resposta que a própria tela consumiu: elimina corrida com outros
    # usuários alterando o ambiente compartilhado entre a chamada e a renderização.
    with admin_page.expect_response(CandidatesPage.CANDIDATES_API_GLOB) as info:
        candidates.goto()
    api_page = ListResponse[CandidateSummary].model_validate(info.value.json())
    allure.attach(
        json.dumps(info.value.json(), indent=2, ensure_ascii=False)[:20_000],
        name="Resposta da API consumida pela tela",
        attachment_type=allure.attachment_type.JSON,
    )

    assert candidates.table.headers() == COLUMNS
    assert candidates.table.records_found() == api_page.meta.total
    ui_rows = [comparable(r) for r in candidates.table.row_values()]
    api_rows = [expected_row(c, core_api) for c in api_page.data]
    assert ui_rows == api_rows
    candidates.attach_screenshot("Lista de candidatos")


@allure.title("Filtro por nome do candidato encontra o candidato consultado via API")
def test_filter_by_candidate_name(
    admin_page: Page, settings: Settings, recruitment_api: RecruitmentApi, core_api: CoreApi
):
    # Ignora candidatos criados pela própria suíte (podem ser limpos durante a execução).
    listed = [
        c
        for c in recruitment_api.list_candidates(limit=50).data
        if not c.last_name.startswith(SUITE_LAST_NAME_PREFIX)
    ]
    if not listed:
        pytest.skip("Ambiente sem candidatos para consultar")
    # Nome único na massa atual evita ambiguidade no autocomplete.
    names = [c.full_name for c in listed]
    target = next((c for c in listed if names.count(c.full_name) == 1), listed[0])
    detail = recruitment_api.get_candidate(target.id)

    page = CandidatesPage(admin_page, settings)
    page.goto()
    page.select_candidate_name(detail.last_name, detail.full_name)
    page.search()

    rows = [comparable(r) for r in page.table.row_values()]
    assert expected_row(target, core_api) in rows
    assert all(r["Candidate"] == detail.full_name for r in rows)
    page.attach_screenshot(f"Filtro por candidato: {detail.full_name}")


@allure.title("Filtro sem correspondência exibe estado vazio")
def test_filter_without_match_shows_empty_state(admin_page: Page, settings: Settings):
    page = CandidatesPage(admin_page, settings)
    page.goto()

    page.fill_keywords("zz-sem-correspondencia-qa-9f8e7d")
    page.search()

    assert page.table.records_found() == 0
    expect(page.table.rows).to_have_count(0)
    page.attach_screenshot("Estado vazio")
