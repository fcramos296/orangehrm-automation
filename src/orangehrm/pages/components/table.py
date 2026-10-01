"""Tabela de listagem (oxd-table) usada em todos os módulos internos."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page

_RECORDS_RE = re.compile(r"\((\d+)\)\s+Records?\s+Found|No Records Found", re.IGNORECASE)


class DataTable:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.root = page.locator(".oxd-table").first
        self.header_cells = self.root.locator(".oxd-table-header .oxd-table-header-cell")
        self.rows: Locator = self.root.locator(".oxd-table-body .oxd-table-card")
        self.records_label = page.locator(".orangehrm-horizontal-padding .oxd-text--span").first
        self.loader = page.locator(".oxd-table-loader, .oxd-loading-spinner")

    def wait_until_loaded(self) -> None:
        self.records_label.wait_for()
        self.loader.first.wait_for(state="hidden")

    def headers(self) -> list[str]:
        """Cabeçalhos visíveis (a coluna de seleção não tem rótulo e é omitida)."""
        return [h for h in self._raw_headers() if h]

    def _raw_headers(self) -> list[str]:
        return [h.strip() for h in self.header_cells.all_inner_texts()]

    def records_found(self) -> int:
        text = self.records_label.inner_text()
        match = _RECORDS_RE.search(text)
        if not match:
            raise AssertionError(f"Contador de registros em formato inesperado: {text!r}")
        return int(match.group(1)) if match.group(1) else 0

    def row_values(self) -> list[dict[str, str]]:
        """Linhas como dicionários ``{cabeçalho: valor}`` (ignora checkbox/ações)."""
        headers = self._raw_headers()
        result: list[dict[str, str]] = []
        for row in self.rows.all():
            cells = [c.strip() for c in row.locator(".oxd-table-cell").all_inner_texts()]
            result.append({h: v for h, v in zip(headers, cells, strict=True) if h})
        return result
