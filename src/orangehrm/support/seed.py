"""Popula um ambiente isolado com massa sintética para a regressão de leitura.

Executado por ``infra/setup.sh``. Cria vagas suficientes para a página pública
paginar (8 por página), candidatos vinculados e timesheets em estados
diferentes, para que nenhum cenário de leitura seja pulado por ausência de massa.
"""

from __future__ import annotations

from datetime import date, timedelta

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


def seed_timesheets(client: ApiClient) -> int:
    """Timesheets submetidos (com e sem lançamentos) e um aprovado, em semanas passadas."""
    # Período semanal começando na segunda; numa instalação nova pode já estar definido.
    client.request.put(client.url("api/v2/time/time-sheet-period"), data={"startDay": 1})

    customer = client.post("api/v2/time/customers", data={"name": "Seed Customer"})["data"]
    project = client.post(
        "api/v2/time/projects",
        data={"name": "Seed Project", "customerId": customer["id"], "projectAdminsEmpNumbers": []},
    )["data"]
    activity = client.post(
        f"api/v2/time/project/{project['id']}/activities", data={"name": "Development"}
    )["data"]

    monday = date.today() - timedelta(days=date.today().weekday())
    plans = [
        ("Paula", "Timesheet", 2, {0: "08:00", 1: "07:30"}, False),
        ("Rafael", "NoEntries", 2, {}, False),
        ("Carla", "Approved", 3, {2: "04:00"}, True),
    ]
    for first, last, weeks_ago, hours, approve in plans:
        emp = client.post(
            "api/v2/pim/employees", data={"firstName": first, "lastName": last, "middleName": ""}
        )["data"]["empNumber"]
        start = monday - timedelta(weeks=weeks_ago)
        sheet = client.post(
            f"api/v2/time/employees/{emp}/timesheets", data={"date": start.isoformat()}
        )["data"]
        if hours:
            dates = {
                (start + timedelta(days=d)).isoformat(): {"duration": v} for d, v in hours.items()
            }
            client.put(
                f"api/v2/time/employees/timesheets/{sheet['id']}/entries",
                data={
                    "entries": [
                        {"projectId": project["id"], "activityId": activity["id"], "dates": dates}
                    ],
                    "deletedEntries": [],
                },
            )
        url = f"api/v2/time/employees/{emp}/timesheets/{sheet['id']}"
        client.put(url, data={"action": "SUBMIT"})
        if approve:
            client.put(url, data={"action": "APPROVE", "comment": "Seed"})
    return len(plans)


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
        timesheets = seed_timesheets(client)
        ctx.dispose()
    print(
        f"Seed concluído: {len(VACANCIES)} vagas, {len(VACANCIES)} candidatos "
        f"e {timesheets} timesheets."
    )


if __name__ == "__main__":
    main()
