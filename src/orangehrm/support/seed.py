"""Popula um ambiente isolado com massa sintética para a regressão de leitura.

Executado por ``infra/setup.sh``. Cria vagas suficientes para a página pública
paginar (8 por página) e candidatos vinculados, para que nenhum cenário de
leitura seja pulado por ausência de massa.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright

from orangehrm.api.client import ApiClient
from orangehrm.api.recruitment import RecruitmentApi
from orangehrm.config.settings import get_settings

VACANCIES = [
    ("Software Engineer", "Desenvolvimento de serviços em Python."),
    ("QA Engineer", "Automação de testes de UI e API."),
    ("Data Analyst", "Análise de indicadores de RH."),
    ("DevOps Engineer", "Pipelines de CI/CD e observabilidade."),
    ("Product Owner", "Gestão do backlog do módulo Recruitment."),
    ("UX Designer", "Pesquisa e prototipação."),
    ("Support Analyst", "Atendimento de segundo nível."),
    ("HR Generalist", "Rotinas de departamento pessoal."),
    ("Payroll Specialist", "Folha de pagamento."),
    ("Security Engineer", "Segurança de aplicações."),
]


def main() -> None:
    settings = get_settings()
    if not settings.allow_write:
        raise SystemExit("Seed exige ORANGEHRM_ALLOW_WRITE=true (ambiente isolado).")

    with sync_playwright() as p:
        ctx = p.request.new_context(timeout=settings.api_timeout_ms)
        client = ApiClient(ctx, settings)
        client.login(settings.admin_username, settings.admin_password.get_secret_value())
        api = RecruitmentApi(client)

        manager = api.list_employees(limit=1).data[0]
        title = api.create_job_title("Seed Job Title")
        for index, (name, description) in enumerate(VACANCIES, start=1):
            vacancy = api.create_vacancy(
                name=f"Seed - {name}",
                job_title_id=title.id,
                hiring_manager_emp_number=manager.emp_number,
                description=description,
            )
            api.create_candidate(
                first_name="Seed",
                last_name=f"Applicant{index:02d}",
                email=f"seed.applicant{index:02d}@example.com",
                vacancy_id=vacancy.id,
            )
        ctx.dispose()
    print(f"Seed concluído: {len(VACANCIES)} vagas e {len(VACANCIES)} candidatos.")


if __name__ == "__main__":
    main()
