"""Contrato e regras da API pública de vagas, consumida pela página de vagas.

Regras verificadas vêm do código da aplicação (VacancyListRestController e
ApplyJobVacancyViewController): apenas vagas ativas e publicadas são listadas,
ordenadas por id decrescente, e o formulário só abre para essas vagas.
"""

from __future__ import annotations

import allure
import pytest

from orangehrm.api.client import ApiClient
from orangehrm.api.recruitment import PublicRecruitmentApi

pytestmark = [pytest.mark.api, allure.feature("Recruitment - API pública de vagas")]


@pytest.fixture(scope="module")
def vacancies(public_api: PublicRecruitmentApi):
    result = public_api.all_vacancies()
    if not result:
        pytest.skip("Ambiente sem vagas publicadas: não há massa para validar a listagem")
    return result


@pytest.mark.smoke
@allure.title("Lista pública retorna apenas vagas ativas e publicadas, com contrato válido")
def test_lists_only_active_and_published_vacancies(public_api: PublicRecruitmentApi, vacancies):
    page = public_api.list_vacancies(limit=50)

    assert page.meta.total == len(vacancies), "meta.total diverge da quantidade paginada"
    inactive = [v.name for v in vacancies if not (v.status and v.is_published)]
    assert not inactive, f"Vagas inativas ou não publicadas expostas publicamente: {inactive}"


@allure.title("Lista pública é ordenada por id decrescente (mais recentes primeiro)")
def test_vacancies_sorted_by_id_desc(vacancies):
    ids = [v.id for v in vacancies]
    assert ids == sorted(ids, reverse=True)


@allure.title("Paginação da API não repete nem perde vagas")
def test_pagination_is_consistent(public_api: PublicRecruitmentApi, vacancies):
    page_size = 3
    paged = []
    for offset in range(0, len(vacancies), page_size):
        paged.extend(public_api.list_vacancies(limit=page_size, offset=offset).data)

    assert [v.id for v in paged] == [v.id for v in vacancies]


@allure.title("Detalhe da vaga pública corresponde ao item da listagem")
def test_vacancy_detail_matches_list(public_api: PublicRecruitmentApi, vacancies):
    for listed in vacancies[:5]:
        with allure.step(f"Comparar vaga {listed.id}"):
            assert public_api.get_vacancy(listed.id) == listed


@allure.title("Vaga inexistente retorna 404 na API pública")
def test_unknown_vacancy_returns_404(anonymous_api: ApiClient, vacancies):
    unknown_id = max(v.id for v in vacancies) + 100_000
    response = anonymous_api.raw_get(f"{PublicRecruitmentApi.BASE}/{unknown_id}")

    assert response.status == 404


@allure.title("Formulário público não abre para vaga inexistente (HTTP 400)")
def test_apply_page_rejects_unknown_vacancy(anonymous_api: ApiClient, vacancies):
    unknown_id = max(v.id for v in vacancies) + 100_000
    response = anonymous_api.raw_get(f"recruitmentApply/applyVacancy/id/{unknown_id}")

    assert response.status == 400


@pytest.mark.smoke
@allure.title("Lista interna de candidatos exige autenticação")
def test_candidates_endpoint_requires_authentication(anonymous_api: ApiClient):
    response = anonymous_api.raw_get("api/v2/recruitment/candidates", params={"limit": 1})

    assert response.status == 401
    assert "data" not in response.json(), "Dados de candidatos expostos sem sessão"
