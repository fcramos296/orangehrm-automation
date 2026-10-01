from __future__ import annotations

import allure

from orangehrm.pages.base_page import BasePage
from orangehrm.pages.components.table import DataTable


class EmployeeTimesheetsPage(BasePage):
    """Time > Timesheets > Employee Timesheets ("Timesheets Pending Action")."""

    PATH = "time/viewEmployeeTimesheet"
    LIST_API_GLOB = "**/api/v2/time/employees/timesheets/list?*"

    def __init__(self, page, settings) -> None:
        super().__init__(page, settings)
        self.table = DataTable(page)

    def wait_until_loaded(self) -> None:
        self.table.wait_until_loaded()

    def view(self, row_index: int) -> None:
        with allure.step(f"Clicar em View na linha {row_index + 1} da listagem"):
            self.table.rows.nth(row_index).get_by_role("button", name="View").click()
