from __future__ import annotations

from dataclasses import dataclass

import allure
from playwright.sync_api import Locator

from orangehrm.pages.base_page import BasePage


@dataclass(frozen=True)
class VacancyCardData:
    title: str
    description: str


class JobBoardPage(BasePage):
    """Página pública de vagas (``/recruitmentApply/jobs.html``)."""

    PATH = "recruitmentApply/jobs.html"
    PAGE_SIZE = 8  # usePaginate({pageSize: 8}) em VacancyList.vue

    @property
    def cards(self) -> Locator:
        return self.page.locator(".orangehrm-card-container").filter(
            has=self.page.locator(".orangehrm-vacancy-card-header")
        )

    @property
    def pagination(self) -> Locator:
        return self.page.locator(".oxd-pagination-page-item")

    @property
    def footer(self) -> Locator:
        return self.page.locator(".orangehrm-copyright-wrapper, .orangehrm-copyright").first

    def wait_until_loaded(self) -> None:
        self.page.locator(".orangehrm-vacancy-list-poweredby").wait_for()
        self.page.locator(".orangehrm-container-loader").wait_for(state="hidden")

    def card(self, title: str) -> Locator:
        return self.cards.filter(
            has=self.page.locator(".oxd-text--card-title", has_text=title)
        ).first

    def visible_vacancies(self) -> list[VacancyCardData]:
        result = []
        for card in self.cards.all():
            title = card.locator(".oxd-text--card-title").inner_text().strip()
            desc = card.locator("pre")
            description = desc.inner_text().strip() if desc.count() else ""
            result.append(VacancyCardData(title=title, description=description))
        return result

    def go_to_page(self, number: int) -> None:
        with allure.step(f"Ir para a página {number} de vagas"):
            self.pagination.filter(has_text=str(number)).first.click()
            self.wait_until_loaded()

    def apply(self, title: str) -> None:
        with allure.step(f"Clicar em Apply na vaga '{title}'"):
            self.card(title).get_by_role("button", name="Apply").click()
