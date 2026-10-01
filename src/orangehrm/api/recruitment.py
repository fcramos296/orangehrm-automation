"""Serviços da API de Recruitment (pública e autenticada)."""

from __future__ import annotations

from collections.abc import Iterator

import allure

from orangehrm.api.client import ApiClient
from orangehrm.api.models import (
    CandidateDetail,
    CandidateHistoryEntry,
    CandidateSummary,
    Employee,
    ItemResponse,
    JobTitle,
    ListResponse,
    PublicVacancy,
    Vacancy,
)


class PublicRecruitmentApi:
    """Endpoints consumidos pela página pública de vagas (sem autenticação)."""

    BASE = "api/v2/recruitment/public/vacancies"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    def list_vacancies(self, limit: int = 50, offset: int = 0) -> ListResponse[PublicVacancy]:
        with allure.step(f"API: listar vagas públicas (limit={limit}, offset={offset})"):
            body = self.client.get(self.BASE, params={"limit": limit, "offset": offset})
            return ListResponse[PublicVacancy].model_validate(body)

    def all_vacancies(self, page_size: int = 50) -> list[PublicVacancy]:
        return list(self._iter_vacancies(page_size))

    def get_vacancy(self, vacancy_id: int) -> PublicVacancy:
        with allure.step(f"API: consultar vaga pública {vacancy_id}"):
            body = self.client.get(f"{self.BASE}/{vacancy_id}")
            return ItemResponse[PublicVacancy].model_validate(body).data

    def _iter_vacancies(self, page_size: int) -> Iterator[PublicVacancy]:
        offset = 0
        while True:
            page = self.list_vacancies(limit=page_size, offset=offset)
            yield from page.data
            offset += page_size
            if offset >= page.meta.total or not page.data:
                return


class RecruitmentApi:
    """Endpoints autenticados do módulo Recruitment (usados pelo admin)."""

    CANDIDATES = "api/v2/recruitment/candidates"
    VACANCIES = "api/v2/recruitment/vacancies"

    def __init__(self, client: ApiClient) -> None:
        self.client = client

    # --- leitura -----------------------------------------------------------

    def list_candidates(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        candidate_name: str | None = None,
        vacancy_id: int | None = None,
        status: int | None = None,
        keywords: str | None = None,
    ) -> ListResponse[CandidateSummary]:
        with allure.step("API: listar candidatos"):
            body = self.client.get(
                self.CANDIDATES,
                params={
                    "limit": limit,
                    "offset": offset,
                    "model": "list",
                    "sortField": "candidate.dateOfApplication",
                    "sortOrder": "DESC",
                    "candidateName": candidate_name,
                    "vacancyId": vacancy_id,
                    "status": status,
                    "keywords": keywords,
                },
            )
            return ListResponse[CandidateSummary].model_validate(body)

    def get_candidate(self, candidate_id: int) -> CandidateDetail:
        with allure.step(f"API: consultar candidato {candidate_id}"):
            body = self.client.get(f"{self.CANDIDATES}/{candidate_id}")
            return ItemResponse[CandidateDetail].model_validate(body).data

    def candidate_history(self, candidate_id: int) -> list[CandidateHistoryEntry]:
        with allure.step(f"API: histórico do candidato {candidate_id}"):
            body = self.client.get(
                f"{self.CANDIDATES}/{candidate_id}/history", params={"limit": 50}
            )
            return ListResponse[CandidateHistoryEntry].model_validate(body).data

    def list_vacancies(self, *, limit: int = 50, name: str | None = None) -> ListResponse[Vacancy]:
        body = self.client.get(self.VACANCIES, params={"limit": limit, "name": name})
        return ListResponse[Vacancy].model_validate(body)

    def list_employees(self, *, limit: int = 1) -> ListResponse[Employee]:
        body = self.client.get("api/v2/pim/employees", params={"limit": limit})
        return ListResponse[Employee].model_validate(body)

    # --- escrita (somente ambiente isolado) ---------------------------------

    def create_job_title(self, title: str) -> JobTitle:
        with allure.step(f"API: criar cargo '{title}'"):
            body = self.client.post("api/v2/admin/job-titles", data={"title": title})
            return ItemResponse[JobTitle].model_validate(body).data

    def delete_job_titles(self, ids: list[int]) -> None:
        with allure.step(f"API: excluir cargos {ids}"):
            self.client.delete("api/v2/admin/job-titles", data={"ids": ids})

    def create_vacancy(
        self,
        *,
        name: str,
        job_title_id: int,
        hiring_manager_emp_number: int,
        description: str,
        num_of_positions: int = 1,
        published: bool = True,
        active: bool = True,
    ) -> Vacancy:
        with allure.step(f"API: criar vaga '{name}'"):
            body = self.client.post(
                self.VACANCIES,
                data={
                    "name": name,
                    "jobTitleId": job_title_id,
                    "employeeId": hiring_manager_emp_number,
                    "description": description,
                    "numOfPositions": num_of_positions,
                    "status": active,
                    "isPublished": published,
                },
            )
            return ItemResponse[Vacancy].model_validate(body).data

    def set_vacancy_published(self, vacancy: Vacancy, *, published: bool) -> Vacancy:
        with allure.step(f"API: {'publicar' if published else 'despublicar'} vaga {vacancy.id}"):
            body = self.client.put(
                f"{self.VACANCIES}/{vacancy.id}",
                data={
                    "name": vacancy.name,
                    "jobTitleId": vacancy.job_title.id if vacancy.job_title else None,
                    "employeeId": vacancy.hiring_manager.id if vacancy.hiring_manager else None,
                    "description": vacancy.description,
                    "numOfPositions": vacancy.num_of_positions,
                    "status": vacancy.status,
                    "isPublished": published,
                },
            )
            return ItemResponse[Vacancy].model_validate(body).data

    def delete_vacancies(self, ids: list[int]) -> None:
        with allure.step(f"API: excluir vagas {ids}"):
            self.client.delete(self.VACANCIES, data={"ids": ids})

    def create_candidate(
        self, *, first_name: str, last_name: str, email: str, vacancy_id: int | None = None
    ) -> int:
        """Cria candidato pelo endpoint interno e retorna o id."""
        with allure.step(f"API: criar candidato '{first_name} {last_name}'"):
            body = self.client.post(
                self.CANDIDATES,
                data={
                    "firstName": first_name,
                    "lastName": last_name,
                    "email": email,
                    "vacancyId": vacancy_id,
                    "consentToKeepData": False,
                },
            )
            return int(body["data"]["id"])

    def delete_candidates(self, ids: list[int]) -> None:
        with allure.step(f"API: excluir candidatos {ids}"):
            self.client.delete(self.CANDIDATES, data={"ids": ids})
