from __future__ import annotations

import allure
from playwright.sync_api import Page

from orangehrm.config.settings import Settings


class BasePage:
    """Base de todos os Page Objects.

    Cada página declara seu ``PATH`` relativo a ``/web/index.php`` e expõe
    ações e consultas de negócio. Asserções ficam nos testes; a página só
    devolve estado observável (texto, listas, locators).
    """

    PATH: str = ""

    def __init__(self, page: Page, settings: Settings) -> None:
        self.page = page
        self.settings = settings

    def url_for(self, path: str | None = None) -> str:
        return f"{self.settings.app_url}/{(path if path is not None else self.PATH).lstrip('/')}"

    def goto(self, path: str | None = None) -> None:
        url = self.url_for(path)
        with allure.step(f"Abrir {url}"):
            self.page.goto(url)
        self.wait_until_loaded()

    def wait_until_loaded(self) -> None:
        """Hook para cada página esperar o elemento que indica que está pronta."""

    def attach_screenshot(self, name: str) -> None:
        allure.attach(
            self.page.screenshot(full_page=True),
            name=name,
            attachment_type=allure.attachment_type.PNG,
        )
