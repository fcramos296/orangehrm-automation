"""Contratos das respostas da API REST v2 do OrangeHRM.

Os modelos validam estrutura e tipos: se a API mudar o formato de forma
incompatível, a desserialização falha e o teste aponta exatamente o campo.
Campos que a aplicação pode omitir são opcionais; campos extras são ignorados
para não quebrar em adições compatíveis.
"""

from __future__ import annotations

from datetime import date
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


T = TypeVar("T")


class ListMeta(ApiModel):
    total: int = Field(ge=0)


class ListResponse(ApiModel, Generic[T]):
    data: list[T]
    meta: ListMeta


class ItemResponse(ApiModel, Generic[T]):
    data: T


# --- Recruitment (público) -------------------------------------------------


class PublicVacancy(ApiModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    description: str | None = None
    num_of_positions: int | None = Field(default=None, alias="numOfPositions")
    status: bool
    is_published: bool = Field(alias="isPublished")


# --- Recruitment (autenticado) ---------------------------------------------


class EmployeeRef(ApiModel):
    id: int | None = None
    emp_number: int | None = Field(default=None, alias="empNumber")
    first_name: str | None = Field(default=None, alias="firstName")
    middle_name: str | None = Field(default=None, alias="middleName")
    last_name: str | None = Field(default=None, alias="lastName")
    termination_id: int | None = Field(default=None, alias="terminationId")

    @property
    def full_name(self) -> str:
        parts = (self.first_name, self.middle_name, self.last_name)
        return " ".join(p for p in parts if p)


class JobTitleRef(ApiModel):
    id: int
    title: str
    is_deleted: bool = Field(default=False, alias="isDeleted")


class VacancyRef(ApiModel):
    id: int
    name: str
    status: bool
    job_title: JobTitleRef | None = Field(default=None, alias="jobTitle")
    hiring_manager: EmployeeRef | None = Field(default=None, alias="hiringManager")


class CandidateStatus(ApiModel):
    id: int
    label: str


class CandidateSummary(ApiModel):
    """Item de `GET /api/v2/recruitment/candidates?model=list`."""

    id: int
    first_name: str = Field(alias="firstName")
    middle_name: str | None = Field(default=None, alias="middleName")
    last_name: str = Field(alias="lastName")
    date_of_application: date | None = Field(default=None, alias="dateOfApplication")
    vacancy: VacancyRef | None = None
    status: CandidateStatus | None = None
    has_attachment: bool = Field(alias="hasAttachment")

    @property
    def full_name(self) -> str:
        parts = (self.first_name, self.middle_name, self.last_name)
        return " ".join(p for p in parts if p)


class CandidateDetail(CandidateSummary):
    email: str
    contact_number: str | None = Field(default=None, alias="contactNumber")
    keywords: str | None = None
    comment: str | None = None
    mode_of_application: int = Field(alias="modeOfApplication")
    consent_to_keep_data: bool = Field(alias="consentToKeepData")


class HistoryAction(ApiModel):
    id: int
    label: str


class CandidateHistoryEntry(ApiModel):
    id: int
    action: HistoryAction
    vacancy_name: str | None = Field(default=None, alias="vacancyName")
    performed_by: EmployeeRef | None = Field(default=None, alias="performedBy")
    performed_date: date = Field(alias="performedDate")
    note: str | None = None


class Vacancy(ApiModel):
    id: int
    name: str
    description: str | None = None
    num_of_positions: int | None = Field(default=None, alias="numOfPositions")
    status: bool
    is_published: bool = Field(alias="isPublished")
    job_title: JobTitleRef | None = Field(default=None, alias="jobTitle")
    hiring_manager: EmployeeRef | None = Field(default=None, alias="hiringManager")


class JobTitle(ApiModel):
    id: int
    title: str


class Employee(ApiModel):
    emp_number: int = Field(alias="empNumber")
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    employee_id: str | None = Field(default=None, alias="employeeId")
    termination_id: int | None = Field(default=None, alias="terminationId")
