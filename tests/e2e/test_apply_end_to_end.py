"""Fluxo completo: vaga publicada -> candidatura pública -> candidato no Recruitment.

Grava dados, portanto roda apenas em ambiente isolado (marcador ``write`` +
``ORANGEHRM_ALLOW_WRITE=true``; o Settings recusa essa flag na demo pública).

Estratégia de isolamento e limpeza:
- a massa (cargo e vaga) é criada via API com sufixo único por teste;
- tudo que o teste cria é removido no teardown via API, mesmo se ele falhar,
  na ordem candidatos -> vaga -> cargo;
- em CI a instância é efêmera (infra/docker-compose.yml) e descartada ao fim.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field

import allure
import pytest
from playwright.sync_api import Page, expect

from orangehrm.api.models import Vacancy
from orangehrm.api.recruitment import RecruitmentApi
from orangehrm.config.settings import Settings
from orangehrm.data import files
from orangehrm.data.applicants import Applicant, build_applicant, unique_tag
from orangehrm.pages.public.apply_vacancy_page import ApplyVacancyPage
from orangehrm.pages.public.job_board_page import JobBoardPage
from orangehrm.pages.recruitment.candidates_page import CandidatesPage

pytestmark = [pytest.mark.e2e, pytest.mark.write, allure.feature("Recruitment - Fluxo completo")]

MODE_ONLINE = 2  # Candidate::MODE_OF_APPLICATION_ONLINE


@dataclass
class Seed:
    vacancy: Vacancy
    candidate_ids: list[int] = field(default_factory=list)


@pytest.fixture
def seed(recruitment_api: RecruitmentApi) -> Generator[Seed, None, None]:
    tag = unique_tag()
    manager = recruitment_api.list_employees(limit=1).data[0]
    job_title = recruitment_api.create_job_title(f"QA Automation Title {tag}")
    vacancy = recruitment_api.create_vacancy(
        name=f"QA Automation Vacancy {tag}",
        job_title_id=job_title.id,
        hiring_manager_emp_number=manager.emp_number,
        description=f"Vaga sintética criada pela suíte ({tag}).",
    )
    data = Seed(vacancy=vacancy)
    yield data

    with allure.step("Limpeza da massa criada pelo teste"):
        created = recruitment_api.list_candidates(vacancy_id=vacancy.id).data
        ids = sorted({*data.candidate_ids, *(c.id for c in created)})
        if ids:
            recruitment_api.delete_candidates(ids)
        recruitment_api.delete_vacancies([vacancy.id])
        recruitment_api.delete_job_titles([job_title.id])


def apply_through_public_site(
    page: Page, settings: Settings, vacancy: Vacancy, applicant: Applicant, tmp_path
) -> None:
    board = JobBoardPage(page, settings)
    board.goto()
    expect(board.card(vacancy.name)).to_be_visible()
    board.apply(vacancy.name)

    form = ApplyVacancyPage(page, settings)
    form.wait_until_loaded()
    form.fill_applicant(applicant)
    form.upload_resume(files.pdf_resume(tmp_path))
    form.submit()

    dialog = form.success_dialog
    expect(dialog.title).to_have_text("Application Received")
    expect(dialog.body).to_have_text("Your application has been submitted successfully")
    form.attach_screenshot("Confirmação de candidatura")
    dialog.button("Ok").click()
    expect(page).to_have_url(f"{settings.app_url}/{JobBoardPage.PATH}")


@pytest.mark.smoke
@allure.title("Candidatura pública cria candidato vinculado à vaga, visível no Recruitment")
def test_public_application_creates_candidate(
    page: Page,
    admin_page: Page,
    settings: Settings,
    recruitment_api: RecruitmentApi,
    seed: Seed,
    tmp_path,
):
    applicant = build_applicant()

    apply_through_public_site(page, settings, seed.vacancy, applicant, tmp_path)

    with allure.step("API: candidato criado com os dados enviados"):
        found = recruitment_api.list_candidates(vacancy_id=seed.vacancy.id).data
        assert len(found) == 1, f"Esperado 1 candidato na vaga, encontrados {len(found)}"
        seed.candidate_ids.append(found[0].id)
        detail = recruitment_api.get_candidate(found[0].id)

        assert detail.full_name == applicant.full_name
        assert detail.email == applicant.email
        assert detail.contact_number == applicant.contact_number
        assert detail.keywords == applicant.keywords
        assert detail.comment == applicant.notes
        assert detail.consent_to_keep_data is True
        assert detail.mode_of_application == MODE_ONLINE
        assert detail.has_attachment is True
        assert detail.vacancy is not None
        assert detail.vacancy.id == seed.vacancy.id
        assert detail.status is not None
        assert detail.status.label == "Application Initiated"

    with allure.step("API: histórico registra a ação 'Applied' na vaga"):
        history = recruitment_api.candidate_history(detail.id)
        assert [(h.action.label, h.vacancy_name) for h in history] == [
            ("Applied", seed.vacancy.name)
        ]

    with allure.step("UI interna: candidato aparece na consulta de Candidates"):
        candidates = CandidatesPage(admin_page, settings)
        candidates.goto()
        candidates.select_candidate_name(applicant.last_name, applicant.full_name)
        candidates.search()
        rows = candidates.table.row_values()
        assert len(rows) == 1
        assert rows[0]["Vacancy"] == seed.vacancy.name
        assert rows[0]["Status"] == "Application Initiated"
        candidates.attach_screenshot("Candidato na consulta interna")


@allure.title("Candidatura sem consentimento é registrada com consentToKeepData = false")
def test_application_without_consent(
    page: Page, settings: Settings, recruitment_api: RecruitmentApi, seed: Seed, tmp_path
):
    applicant = build_applicant(consent_to_keep_data=False)

    apply_through_public_site(page, settings, seed.vacancy, applicant, tmp_path)

    found = recruitment_api.list_candidates(vacancy_id=seed.vacancy.id).data
    assert len(found) == 1
    seed.candidate_ids.append(found[0].id)
    assert recruitment_api.get_candidate(found[0].id).consent_to_keep_data is False


@allure.title("Vaga despublicada some da página pública e o formulário deixa de abrir")
def test_unpublished_vacancy_is_not_offered(
    page: Page, settings: Settings, recruitment_api: RecruitmentApi, seed: Seed
):
    recruitment_api.set_vacancy_published(seed.vacancy, published=False)

    board = JobBoardPage(page, settings)
    board.goto()
    expect(board.card(seed.vacancy.name)).to_have_count(0)

    response = page.request.get(
        f"{settings.app_url}/recruitmentApply/applyVacancy/id/{seed.vacancy.id}"
    )
    assert response.status == 400
