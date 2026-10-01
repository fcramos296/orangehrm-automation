"""Configurações globais que mudam a forma como a tela exibe os dados.

A demo pública é compartilhada: formato de data e textos podem ser alterados
por qualquer visitante (ex.: data em ``Y-d-m``). Os testes leem essas
configurações da própria aplicação em vez de fixar valores.
"""

from __future__ import annotations

from datetime import date
from functools import cached_property

import allure

from orangehrm.api.client import ApiClient

# Tokens de data do PHP usados pelo OrangeHRM -> strftime do Python.
_PHP_TO_STRFTIME = {
    "Y": "%Y",
    "y": "%y",
    "m": "%m",
    "n": "{n}",
    "d": "%d",
    "j": "{j}",
    "M": "%b",
    "F": "%B",
    "D": "%a",
    "l": "%A",
}


class CoreApi:
    def __init__(self, client: ApiClient) -> None:
        self.client = client

    @cached_property
    def date_format(self) -> str:
        """Formato de data configurado em Admin > Localization (sintaxe PHP)."""
        with allure.step("API: consultar formato de data (Admin > Localization)"):
            return self.client.get("api/v2/admin/localization")["data"]["dateFormat"]

    @cached_property
    def messages(self) -> dict[str, str]:
        """Textos da interface no idioma atual (target, ou source sem tradução)."""
        with allure.step("API: carregar textos da interface (i18n)"):
            raw = self.client.get("core/i18n/messages")
        return {key: (v.get("target") or v.get("source") or "") for key, v in raw.items()}

    def text(self, key: str) -> str:
        return self.messages[key].strip()

    def format_date(self, value: date) -> str:
        pattern = "".join(_PHP_TO_STRFTIME.get(ch, ch) for ch in self.date_format)
        return value.strftime(pattern).format(n=value.month, j=value.day)
