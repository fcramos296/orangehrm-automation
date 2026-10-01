"""Página pública de vagas: o candidato precisa encontrar as vagas abertas e
chegar ao formulário certo. A API pública é a fonte de verdade (API first)."""

from __future__ import annotations

import math

import allure
import pytest
from playwright.sync_api import Page, expect

from orangehrm.api.recruitment import PublicRecruitmentApi
from orangehrm.config.settings import Settings
from orangehrm.pages.public.apply_vacancy_page import ApplyVacancyPage
from orangehrm.pages.public.job_board_page import JobBoardPage

pytestmark = [pytest.mark.ui, allure.feature("Recruitment - Página pública de vagas")]


@pytest.fixture
def job_board(page: Page, settings: Settings) -> JobBoardPage:
    board = JobBoardPage(page, settings)
    board.goto()
    return board


@pytest.fixture(scope="module")
def published(public_api: PublicRecruitmentApi):
    vacancies = public_api.all_vacancies()
    if not vacancies:
        pytest.skip("Ambiente sem vagas publicadas")
    return vacancies


@pytest.mark.smoke
@allure.title("Página de vagas exibe as vagas publicadas na mesma ordem da API")
def test_board_shows_published_vacancies(job_board: JobBoardPage, published):
    expected = [v.name for v in published[: JobBoardPage.PAGE_SIZE]]

    expect(job_board.cards).to_have_count(len(expected))
    assert [c.title for c in job_board.visible_vacancies()] == expected
    job_board.attach_screenshot("Página pública de vagas")


@allure.title("Paginação da página de vagas cobre todas as vagas publicadas")
def test_board_pagination_covers_all_vacancies(job_board: JobBoardPage, published):
    pages = math.ceil(len(published) / JobBoardPage.PAGE_SIZE)
    if pages < 2:
        expect(job_board.pagination).to_have_count(0)
        pytest.skip(f"{len(published)} vaga(s): paginação não é exibida com uma página")

    seen = [c.title for c in job_board.visible_vacancies()]
    for number in range(2, pages + 1):
        job_board.go_to_page(number)
        seen.extend(c.title for c in job_board.visible_vacancies())

    assert seen == [v.name for v in published]


@pytest.mark.smoke
@allure.title("Botão Apply leva ao formulário da vaga escolhida")
def test_apply_opens_form_of_selected_vacancy(
    job_board: JobBoardPage, page: Page, settings: Settings, published
):
    vacancy = published[0]

    job_board.apply(vacancy.name)
    form = ApplyVacancyPage(page, settings)
    form.wait_until_loaded()

    expect(page).to_have_url(ApplyVacancyPage.URL_RE)
    assert ApplyVacancyPage.URL_RE.search(page.url).group(1) == str(vacancy.id)
    expect(form.heading).to_have_text(f"Apply for {vacancy.name}")
    if vacancy.description:
        expect(form.description).to_contain_text(vacancy.description.strip().splitlines()[0])
    expect(form.resume_hint).to_have_text("Accepts .docx, .doc, .odt, .pdf, .rtf, .txt up to 1MB")
    form.attach_screenshot("Formulário de candidatura")


@allure.title("Botão Back do formulário volta para a página de vagas")
def test_back_returns_to_board(page: Page, settings: Settings, published):
    form = ApplyVacancyPage(page, settings)
    form.open(published[0].id)

    form.back_button.click()

    expect(page).to_have_url(f"{settings.app_url}/{JobBoardPage.PATH}")
