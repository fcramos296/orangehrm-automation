from __future__ import annotations

import re
from pathlib import Path

import allure
from playwright.sync_api import Locator

from orangehrm.data.applicants import Applicant
from orangehrm.pages.base_page import BasePage
from orangehrm.pages.components.form import Dialog, FormField

SUBMIT_ENDPOINT_GLOB = "**/recruitment/public/applicants"


class ApplyVacancyPage(BasePage):
    """Formulário público de candidatura (``/recruitmentApply/applyVacancy/id/{id}``)."""

    PATH = "recruitmentApply/applyVacancy/id/{vacancy_id}"
    URL_RE = re.compile(r"/recruitmentApply/applyVacancy/id/(\d+)")

    FIELDS = (
        "firstName",
        "middleName",
        "lastName",
        "email",
        "contactNumber",
        "resume",
        "keywords",
        "comment",
    )

    def open(self, vacancy_id: int) -> None:
        self.goto(self.PATH.format(vacancy_id=vacancy_id))

    def wait_until_loaded(self) -> None:
        # O título só recebe o nome da vaga após o GET da API pública.
        self.heading.filter(has_text=re.compile(r"Apply for \S")).wait_for()

    # --- elementos ---------------------------------------------------------

    @property
    def heading(self) -> Locator:
        return self.page.locator(".orangehrm-main-title")

    @property
    def description(self) -> Locator:
        return self.page.locator(".orangehrm-vacancy-description pre")

    @property
    def resume_hint(self) -> Locator:
        return self.page.locator(".orangehrm-input-hint")

    @property
    def consent_checkbox(self) -> Locator:
        return self.page.locator("[name='consentToKeepData']")

    @property
    def submit_button(self) -> Locator:
        return self.page.get_by_role("button", name="Submit")

    @property
    def back_button(self) -> Locator:
        return self.page.get_by_role("button", name="Back")

    @property
    def errors(self) -> Locator:
        return self.page.locator(".oxd-input-field-error-message")

    @property
    def success_dialog(self) -> Dialog:
        return Dialog(self.page)

    def field(self, name: str) -> FormField:
        if name not in self.FIELDS:
            raise ValueError(f"Campo desconhecido: {name}")
        return FormField(self.page, name)

    # --- ações -------------------------------------------------------------

    def fill_applicant(self, applicant: Applicant) -> None:
        with allure.step(f"Preencher candidatura de {applicant.full_name} <{applicant.email}>"):
            values = {
                "firstName": applicant.first_name,
                "middleName": applicant.middle_name,
                "lastName": applicant.last_name,
                "email": applicant.email,
                "contactNumber": applicant.contact_number,
                "keywords": applicant.keywords,
                "comment": applicant.notes,
            }
            for name, value in values.items():
                if value:
                    self.field(name).fill(value)
            self.set_consent(applicant.consent_to_keep_data)

    def set_consent(self, checked: bool) -> None:
        if self.consent_checkbox.is_checked() != checked:
            # O input nativo é oculto pelo componente oxd; clica-se no rótulo visual.
            self.page.locator(".oxd-checkbox-wrapper").filter(has=self.consent_checkbox).locator(
                ".oxd-checkbox-input"
            ).click()

    def upload_resume(self, file: Path) -> None:
        with allure.step(f"Anexar currículo {file.name} ({file.stat().st_size} bytes)"):
            self.field("resume").input.set_input_files(file)

    def submit(self) -> None:
        with allure.step("Clicar em Submit"):
            self.submit_button.click()

    def error_messages(self) -> dict[str, str]:
        """Mensagens de validação visíveis, por campo."""
        messages = {name: self.field(name).error_text() for name in self.FIELDS}
        return {name: text for name, text in messages.items() if text is not None}
