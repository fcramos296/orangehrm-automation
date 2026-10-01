"""Componentes de formulário da biblioteca de UI do OrangeHRM (oxd)."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

# Ancestral mais próximo que agrupa label, input e mensagem de erro do campo.
_FIELD_GROUP_XPATH = (
    "xpath=ancestor::div"
    "[contains(concat(' ', normalize-space(@class), ' '), ' oxd-input-group ')][1]"
)


class FormField:
    """Campo identificado pelo atributo ``name``, estável entre versões do front-end."""

    def __init__(self, page: Page, name: str) -> None:
        self.page = page
        self.name = name
        self.input: Locator = page.locator(f"[name='{name}']")
        self.group: Locator = self.input.locator(_FIELD_GROUP_XPATH)
        self.error: Locator = self.group.locator(".oxd-input-field-error-message")

    def fill(self, value: str) -> None:
        self.input.fill(value)
        # A validação do oxd roda no blur/mudança; o Tab garante o disparo.
        self.input.press("Tab")

    def error_text(self) -> str | None:
        return self.error.inner_text() if self.error.count() else None


class Dialog:
    def __init__(self, page: Page) -> None:
        self.root = page.locator(".oxd-dialog-sheet")
        self.title = self.root.locator(".orangehrm-modal-header")
        self.body = self.root.locator(".orangehrm-text-center-align")

    def button(self, name: str) -> Locator:
        return self.root.get_by_role("button", name=name)
