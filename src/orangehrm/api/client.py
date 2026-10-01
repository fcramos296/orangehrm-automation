"""Cliente HTTP base sobre o `APIRequestContext` do Playwright.

Usar o mesmo motor da UI permite compartilhar a sessão autenticada
(`storage_state`) entre API e navegador e coloca as chamadas no mesmo trace.
"""

from __future__ import annotations

import html
import re
from typing import Any

import allure
from playwright.sync_api import APIRequestContext, APIResponse

from orangehrm.config.settings import Settings

_LOGIN_TOKEN_RE = re.compile(r':token="([^"]+)"')


class ApiError(AssertionError):
    """Resposta inesperada da API; carrega status e corpo para diagnóstico."""

    def __init__(self, method: str, url: str, response: APIResponse) -> None:
        self.status = response.status
        body = response.text()[:1_000]
        super().__init__(f"{method} {url} -> HTTP {response.status}: {body}")


class ApiClient:
    def __init__(self, request: APIRequestContext, settings: Settings) -> None:
        self._request = request
        self.settings = settings

    @property
    def request(self) -> APIRequestContext:
        return self._request

    def url(self, path: str) -> str:
        return f"{self.settings.app_url}/{path.lstrip('/')}"

    # --- autenticação --------------------------------------------------------

    def login(self, username: str, password: str) -> None:
        """Autentica pelo mesmo endpoint do formulário de login (cookie de sessão).

        A API v2 do OrangeHRM não expõe login por token para o front-end: o
        formulário envia um CSRF token renderizado na página para /auth/validate.
        """
        with allure.step(f"API: autenticar como {username}"):
            page = self._request.get(self.url("auth/login"))
            match = _LOGIN_TOKEN_RE.search(page.text())
            if not match:
                raise AssertionError("CSRF token não encontrado na página de login")
            token = html.unescape(match.group(1)).strip('"')
            response = self._request.post(
                self.url("auth/validate"),
                form={"_token": token, "username": username, "password": password},
            )
            if not response.ok or "/auth/login" in response.url:
                raise AssertionError(f"Login via API falhou (URL final: {response.url})")

    # --- verbos --------------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None, expected: int = 200) -> Any:
        return self._send("GET", path, params=params, expected=expected)

    def post(self, path: str, data: dict[str, Any], expected: int = 200) -> Any:
        return self._send("POST", path, data=data, expected=expected)

    def put(self, path: str, data: dict[str, Any], expected: int = 200) -> Any:
        return self._send("PUT", path, data=data, expected=expected)

    def delete(self, path: str, data: dict[str, Any], expected: int = 200) -> Any:
        return self._send("DELETE", path, data=data, expected=expected)

    def raw_get(self, path: str, params: dict[str, Any] | None = None) -> APIResponse:
        return self._request.get(self.url(path), params=_clean(params))

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        expected: int,
    ) -> Any:
        url = self.url(path)
        response = self._request.fetch(url, method=method, params=_clean(params), data=data)
        if response.status != expected:
            raise ApiError(method, url, response)
        return response.json() if response.body() else None


def _clean(params: dict[str, Any] | None) -> dict[str, str | float | bool] | None:
    """Remove filtros vazios: a API rejeita parâmetros com valor nulo."""
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}
