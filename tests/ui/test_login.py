from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page, expect

from orangehrm.config.settings import Settings
from orangehrm.pages.login_page import LoginPage

pytestmark = [pytest.mark.ui, allure.feature("Autenticação")]


@pytest.mark.smoke
@allure.title("Login com credenciais válidas abre o Dashboard")
def test_login_with_valid_credentials(page: Page, settings: Settings):
    login = LoginPage(page, settings)
    login.goto()

    login.login(settings.admin_username, settings.admin_password.get_secret_value())

    expect(page).to_have_url(f"{settings.app_url}/dashboard/index")
    expect(page.locator(".oxd-topbar-header-breadcrumb")).to_have_text("Dashboard")


@allure.title("Login com senha inválida exibe 'Invalid credentials'")
def test_login_with_invalid_password(page: Page, settings: Settings):
    login = LoginPage(page, settings)
    login.goto()

    login.login(settings.admin_username, "senha-invalida-qa")

    expect(login.alert).to_have_text("Invalid credentials")
    expect(page).to_have_url(f"{settings.app_url}/auth/login")
