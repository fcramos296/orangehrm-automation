from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator

from orangehrm.pages.base_page import BasePage

_STATUS_RE = re.compile(r"Status:\s*(.+)")


class TimesheetDetailPage(BasePage):
    """Detalhe de timesheet de um funcionário (``/time/viewTimesheet/employeeId/{n}``).

    A tela não recebe o id do timesheet: busca pelo funcionário e pela data
    ``startDate`` da URL (endpoint ``/api/v2/time/timesheets/default``).
    """

    PATH = "time/viewTimesheet/employeeId/{emp_number}?startDate={start_date}"
    DEFAULT_API_GLOB = "**/api/v2/time/timesheets/default?*"

    def open(self, emp_number: int, start_date: str) -> None:
        self.goto(self.PATH.format(emp_number=emp_number, start_date=start_date))

    def wait_until_loaded(self) -> None:
        self.page.locator(".orangehrm-timesheet-header").wait_for()
        self.page.locator(".orangehrm-timesheet-loader").wait_for(state="hidden")

    @property
    def title(self) -> Locator:
        return self.page.locator(".orangehrm-timesheet-header--title .orangehrm-main-title")

    @property
    def period_input(self) -> Locator:
        return self.page.locator(".orangehrm-timeperiod-picker input")

    @property
    def previous_button(self) -> Locator:
        return self.page.locator(".orangehrm-timeperiod-icon.--prev")

    @property
    def next_button(self) -> Locator:
        return self.page.locator(".orangehrm-timeperiod-icon.--next")

    @property
    def body_message(self) -> Locator:
        """Mensagem quando não há timesheet ou lançamentos no período."""
        return self.page.locator(
            ".orangehrm-timesheet-body-message, .orangehrm-timesheet-table-body-cell[colspan]"
        ).first

    @property
    def entry_rows(self) -> Locator:
        return self.page.locator(".orangehrm-timesheet-table-body-row:not(.--total)").filter(
            has=self.page.locator(".--freeze-right")
        )

    @property
    def grand_total(self) -> Locator:
        return self.page.locator(".orangehrm-timesheet-table-body-row.--total .--freeze-right")

    @property
    def footer_title(self) -> Locator:
        return self.page.locator(".orangehrm-timesheet-footer--title")

    @property
    def action_log_table(self) -> Locator:
        return self.page.locator(".oxd-table").last

    def period_text(self) -> str:
        return self.period_input.input_value()

    def status_text(self) -> str | None:
        if not self.footer_title.count():
            return None
        match = _STATUS_RE.search(self.footer_title.inner_text())
        return match.group(1).strip() if match else None

    def action_log_rows(self) -> list[list[str]]:
        rows = self.action_log_table.locator(".oxd-table-card")
        return [
            [c.strip() for c in row.locator(".oxd-table-cell").all_inner_texts()]
            for row in rows.all()
        ]

    def go_previous(self) -> None:
        with allure.step("Clicar em período anterior"):
            self.previous_button.click()

    def go_next(self) -> None:
        with allure.step("Clicar em próximo período"):
            self.next_button.click()
