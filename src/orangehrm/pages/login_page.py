from __future__ import annotations

import allure
from playwright.sync_api import Locator

from orangehrm.pages.base_page import BasePage


class LoginPage(BasePage):
    PATH = "auth/login"

    def wait_until_loaded(self) -> None:
        self.username.wait_for()

    @property
    def username(self) -> Locator:
        return self.page.locator("input[name='username']")

    @property
    def password(self) -> Locator:
        return self.page.locator("input[name='password']")

    @property
    def alert(self) -> Locator:
        return self.page.locator(".oxd-alert-content-text")

    def login(self, username: str, password: str) -> None:
        with allure.step(f"Login na UI como {username}"):
            self.username.fill(username)
            self.password.fill(password)
            self.page.get_by_role("button", name="Login").click()
