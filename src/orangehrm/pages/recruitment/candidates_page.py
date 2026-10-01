from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator

from orangehrm.pages.base_page import BasePage
from orangehrm.pages.components.table import DataTable


class CandidatesPage(BasePage):
    """Recruitment > Candidates (``/recruitment/viewCandidates``). Somente consulta."""

    PATH = "recruitment/viewCandidates"
    CANDIDATES_API_GLOB = "**/api/v2/recruitment/candidates?*"

    def __init__(self, page, settings) -> None:
        super().__init__(page, settings)
        self.table = DataTable(page)

    def wait_until_loaded(self) -> None:
        self.page.locator(".oxd-table-filter").wait_for()
        self.table.wait_until_loaded()

    @property
    def filter_panel(self) -> Locator:
        return self.page.locator(".oxd-table-filter")

    def _filter_group(self, label: str) -> Locator:
        return self.filter_panel.locator(".oxd-input-group").filter(
            has=self.page.locator("label", has_text=label)
        )

    def select_candidate_name(self, hint: str, full_name: str) -> None:
        """Digita ``hint`` no autocomplete e escolhe a sugestão ``full_name``.

        O autocomplete busca por LIKE em primeiro, meio OU último nome
        separadamente (CandidateDao); digitar o nome completo não retorna
        sugestões. Por isso o filtro recebe uma parte do nome como dica.
        """
        with allure.step(f"Filtrar por Candidate Name: digitar '{hint}', escolher '{full_name}'"):
            field = self._filter_group("Candidate Name").locator("input")
            field.fill(hint)
            # A sugestão junta primeiro/meio/último nome; sem nome do meio sobra
            # espaço duplo, então a comparação normaliza espaços.
            pattern = r"\s+".join(re.escape(part) for part in full_name.split())
            option = self.page.locator(".oxd-autocomplete-option").filter(
                has_text=re.compile(rf"^\s*{pattern}\s*$")
            )
            option.first.click()

    def fill_keywords(self, keywords: str) -> None:
        with allure.step(f"Filtrar por Keywords = '{keywords}'"):
            self._filter_group("Keywords").locator("input").fill(keywords)

    def search(self) -> None:
        with allure.step("Clicar em Search"):
            with self.page.expect_response(self.CANDIDATES_API_GLOB):
                self.filter_panel.get_by_role("button", name="Search").click()
            self.table.wait_until_loaded()

    def reset(self) -> None:
        with allure.step("Clicar em Reset"):
            with self.page.expect_response(self.CANDIDATES_API_GLOB):
                self.filter_panel.get_by_role("button", name="Reset").click()
            self.table.wait_until_loaded()
