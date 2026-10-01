"""Dados sintéticos de candidatos.

Nenhum dado pessoal real: nomes fictícios, e-mails no domínio reservado
``example.com`` (RFC 2606) e um sufixo único por execução, para que cada
cenário seja rastreável e não colida com execuções paralelas.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class Applicant(BaseModel):
    first_name: str = Field(max_length=30)
    middle_name: str = Field(default="", max_length=30)
    last_name: str = Field(max_length=30)
    email: str = Field(max_length=50)
    contact_number: str = Field(default="", max_length=25)
    keywords: str = Field(default="", max_length=250)
    notes: str = Field(default="", max_length=250)
    consent_to_keep_data: bool = False

    @property
    def full_name(self) -> str:
        parts = (self.first_name, self.middle_name, self.last_name)
        return " ".join(p for p in parts if p)


SUITE_LAST_NAME_PREFIX = "Candidate"  # sobrenome dos candidatos criados pela suíte


def unique_tag() -> str:
    return uuid.uuid4().hex[:8]


def build_applicant(**overrides: object) -> Applicant:
    tag = unique_tag()
    data: dict[str, object] = {
        "first_name": "Qa",
        "middle_name": "Auto",
        "last_name": f"{SUITE_LAST_NAME_PREFIX}{tag}",
        "email": f"qa.candidate.{tag}@example.com",
        "contact_number": "+55 (51) 3000-0000",
        "keywords": f"automation, playwright, qa-{tag}",
        "notes": "Candidatura sintética gerada pela suíte de regressão.",
        "consent_to_keep_data": True,
    }
    data.update(overrides)
    return Applicant.model_validate(data)
