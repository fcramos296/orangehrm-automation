from __future__ import annotations

import pytest
from playwright.sync_api import Page, Request

from orangehrm.api.recruitment import PublicRecruitmentApi
from orangehrm.config.settings import Settings
from orangehrm.pages.public.apply_vacancy_page import ApplyVacancyPage


class SubmissionSpy:
    """Registra toda requisição de envio de candidatura feita pela página.

    Nos cenários negativos, prova que a validação bloqueou o envio e que o
    ambiente compartilhado não recebeu nenhum dado.
    """

    def __init__(self, page: Page) -> None:
        self.requests: list[Request] = []
        page.on("request", self._on_request)

    def _on_request(self, request: Request) -> None:
        if request.method == "POST" and request.url.endswith("/recruitment/public/applicants"):
            self.requests.append(request)


@pytest.fixture(scope="session")
def target_vacancy(public_api: PublicRecruitmentApi):
    vacancies = public_api.list_vacancies(limit=1).data
    if not vacancies:
        pytest.skip("Ambiente sem vagas publicadas: formulário público indisponível")
    return vacancies[0]


@pytest.fixture
def submission_spy(page: Page) -> SubmissionSpy:
    return SubmissionSpy(page)


@pytest.fixture
def apply_form(
    page: Page, settings: Settings, target_vacancy, submission_spy: SubmissionSpy
) -> ApplyVacancyPage:
    form = ApplyVacancyPage(page, settings)
    form.open(target_vacancy.id)
    return form
