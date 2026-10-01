"""Serviços da API do módulo Time (somente leitura)."""

from __future__ import annotations

from datetime import date

import allure

from orangehrm.api.client import ApiClient
from orangehrm.api.models import (
    ItemResponse,
    ListResponse,
    PendingTimesheet,
    Timesheet,
    TimesheetActionLog,
    TimesheetEntries,
)


class TimeApi:
    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def pending_timesheets(
        self, *, limit: int = 50, offset: int = 0
    ) -> ListResponse[PendingTimesheet]:
        """Lista "Timesheets Pending Action" (Time > Timesheets > Employee Timesheets)."""
        with allure.step("API: listar timesheets pendentes de ação"):
            body = self.client.get(
                "api/v2/time/employees/timesheets/list", params={"limit": limit, "offset": offset}
            )
            return ListResponse[PendingTimesheet].model_validate(body)

    def timesheet_for_date(self, emp_number: int, day: date) -> Timesheet:
        """Mesma busca que a tela de detalhe faz: timesheet do período que contém ``day``."""
        with allure.step(f"API: timesheet do funcionário {emp_number} em {day}"):
            body = self.client.get(
                "api/v2/time/timesheets/default",
                params={"date": day.isoformat(), "empNumber": emp_number},
            )
            return ItemResponse[Timesheet].model_validate(body).data

    def entries(self, timesheet_id: int) -> TimesheetEntries:
        with allure.step(f"API: lançamentos do timesheet {timesheet_id}"):
            body = self.client.get(f"api/v2/time/employees/timesheets/{timesheet_id}/entries")
            return TimesheetEntries.model_validate(body)

    def action_logs(self, timesheet_id: int) -> list[TimesheetActionLog]:
        with allure.step(f"API: histórico de ações do timesheet {timesheet_id}"):
            body = self.client.get(
                f"api/v2/time/timesheets/{timesheet_id}/action-logs", params={"limit": 50}
            )
            return ListResponse[TimesheetActionLog].model_validate(body).data
