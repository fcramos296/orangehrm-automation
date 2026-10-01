"""Coleta evidências (prints + dados da API) na demo pública, somente leitura.

Apoia o documento de evidências das Atividades 1 e 2: navega pelas telas
citadas no desafio, registra versão e data e compara listagem x detalhe de
timesheets. Nenhum botão que grava dados (Save, Approve, Reject, Hire...) é
acionado; formulários são apenas abertos para mostrar os campos.

Uso: python tools/evidence/capture_demo.py [pasta_saida]
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Route, sync_playwright

from orangehrm.api.client import ApiClient
from orangehrm.config.settings import get_settings

STATUS_HIRED = 9
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence-output")
SETTINGS = get_settings()
APP = SETTINGS.app_url
DATA: dict[str, Any] = {"errors": []}


def shot(page: Page, name: str, full: bool = True) -> None:
    page.wait_for_timeout(600)
    page.screenshot(path=OUT / f"{name}.png", full_page=full)


def highlight(page: Page, selector: str, index: int = 0) -> None:
    page.evaluate(
        """([sel, i]) => {
            const el = document.querySelectorAll(sel)[i];
            if (el) { el.style.outline = '3px solid #e53935'; el.style.outlineOffset = '2px'; }
        }""",
        [selector, index],
    )


def step(name: str):
    def deco(fn):
        def run(*args, **kwargs):
            print(f">> {name}")
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - coleta continua nas demais telas
                DATA["errors"].append({"step": name, "error": repr(exc)})
                traceback.print_exc()
                return None

        return run

    return deco


def wait_table(page: Page) -> None:
    page.locator(".orangehrm-horizontal-padding .oxd-text--span").first.wait_for()
    page.wait_for_timeout(800)


# --- geral --------------------------------------------------------------------


@step("Ambiente")
def environment(page: Page, api: ApiClient) -> None:
    # Contexto sem sessão: com a sessão ativa a página de login redireciona.
    anonymous = page.context.browser.new_context(viewport={"width": 1440, "height": 900})
    login = anonymous.new_page()
    login.goto(f"{APP}/auth/login")
    login.locator("input[name='username']").wait_for()
    footer = login.locator(".orangehrm-copyright-wrapper").inner_text()
    DATA["environment"] = {
        "url": str(SETTINGS.base_url),
        "footer": " ".join(footer.split()),
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "localization": api.get("api/v2/admin/localization")["data"],
        "timesheet_period": api.get("api/v2/time/time-sheet-period")["data"],
    }
    shot(login, "00_login")
    anonymous.close()


# --- Atividade 1: Recruitment -> PIM -------------------------------------------


@step("Recruitment: candidatos e status")
def recruitment(page: Page, api: ApiClient) -> None:
    candidates = api.get("api/v2/recruitment/candidates", params={"limit": 200, "model": "list"})
    statuses = Counter(
        (c.get("status") or {}).get("label", "(sem vaga)") for c in candidates["data"]
    )
    DATA["recruitment"] = {
        "total_candidates": candidates["meta"]["total"],
        "status_distribution_first_200": dict(statuses),
        "statuses": api.get("api/v2/recruitment/candidates/statuses")["data"],
    }
    page.goto(f"{APP}/recruitment/viewCandidates")
    wait_table(page)
    shot(page, "10_candidates_list")

    samples: dict[str, Any] = {}
    by_status: dict[str, dict] = {}
    for cand in candidates["data"]:
        label = (cand.get("status") or {}).get("label")
        if label and label not in by_status:
            by_status[label] = cand
    for label, cand in by_status.items():
        allowed = api.get(f"api/v2/recruitment/candidates/{cand['id']}/actions/allowed")
        detail = api.get(f"api/v2/recruitment/candidates/{cand['id']}")["data"]
        samples[label] = {
            "candidate_id": cand["id"],
            "vacancy": (cand.get("vacancy") or {}).get("name"),
            "allowed_actions": [a.get("label") for a in allowed["data"]],
            "consentToKeepData": detail.get("consentToKeepData"),
            "has_email": bool(detail.get("email")),
        }
    DATA["recruitment"]["samples_by_status"] = samples

    for label in ("Hired", "Application Initiated", "Job Offered", "Interview Passed"):
        if label in by_status:
            cid = by_status[label]["id"]
            page.goto(f"{APP}/recruitment/addCandidate/{cid}")
            page.locator(
                ".orangehrm-recruitment-status, .orangehrm-card-container"
            ).first.wait_for()
            page.wait_for_timeout(1200)
            slug = re.sub(r"\W+", "_", label.lower())
            shot(page, f"11_candidate_{slug}")

    hired = [c for c in candidates["data"] if (c.get("status") or {}).get("id") == STATUS_HIRED]
    links = []
    for cand in hired[:10]:
        found = api.get(
            "api/v2/pim/employees",
            params={"nameOrId": cand["lastName"], "limit": 50, "includeEmployees": "onlyCurrent"},
        )
        names = [f"{e['firstName']} {e['lastName']}" for e in found["data"]]
        links.append(
            {
                "candidate": f"{cand['firstName']} {cand['lastName']}",
                "candidate_id": cand["id"],
                "employees_with_same_last_name": names,
            }
        )
    DATA["recruitment"]["hired_vs_pim"] = links

    if hired:
        cid = hired[0]["id"]
        page.goto(f"{APP}/recruitment/candidateHistory/{cid}/0")
        page.wait_for_timeout(500)
        history = api.get(f"api/v2/recruitment/candidates/{cid}/history", params={"limit": 50})
        DATA["recruitment"]["hired_history_example"] = [
            {"action": h["action"]["label"], "date": h["performedDate"]} for h in history["data"]
        ]


@step("Recruitment: tela da ação Hire (sem salvar)")
def hire_action_form(page: Page, api: ApiClient) -> None:
    offered = api.get(
        "api/v2/recruitment/candidates", params={"limit": 50, "model": "list", "status": 7}
    )["data"]
    if not offered:
        DATA.setdefault("recruitment", {})["hire_form"] = "sem candidato em Job Offered"
        return
    cid = offered[0]["id"]
    page.goto(f"{APP}/recruitment/addCandidate/{cid}")
    page.get_by_role("button", name="Hire").wait_for()
    shot(page, "12_candidate_job_offered_actions")
    page.get_by_role("button", name="Hire").click()
    page.wait_for_url("**/changeCandidateVacancyStatus**")
    page.wait_for_timeout(1500)
    shot(page, "13_hire_action_form")
    DATA.setdefault("recruitment", {})["hire_form_url"] = page.url


@step("PIM, Add Employee e Directory")
def pim_directory(page: Page, api: ApiClient) -> None:
    page.goto(f"{APP}/pim/viewEmployeeList")
    wait_table(page)
    shot(page, "14_pim_employee_list")
    page.goto(f"{APP}/pim/addEmployee")
    page.locator("input[name='firstName']").wait_for()
    page.wait_for_timeout(1000)
    employee_id = page.locator(
        ".oxd-input-group", has=page.locator("label", has_text="Employee Id")
    )
    DATA["pim"] = {
        "add_employee_generated_id": employee_id.locator("input").input_value(),
        "add_employee_fields": [
            " ".join(t.split()) for t in page.locator("form label").all_inner_texts()
        ],
    }
    shot(page, "15_pim_add_employee")
    page.goto(f"{APP}/directory/viewDirectory")
    page.locator(".orangehrm-directory-card, .oxd-sheet").first.wait_for()
    page.wait_for_timeout(1500)
    shot(page, "16_directory", full=False)


# --- Atividade 2: Time -------------------------------------------------------------


@step("Time: listagem x detalhe")
def timesheets(page: Page, api: ApiClient) -> None:
    listing = api.get("api/v2/time/employees/timesheets/list", params={"limit": 50})
    items = listing["data"]
    comparisons = []
    for item in items:
        emp = item["employee"]["empNumber"]
        default = api.get(
            "api/v2/time/timesheets/default", params={"date": item["startDate"], "empNumber": emp}
        )["data"]
        entries = api.get(f"api/v2/time/employees/timesheets/{item['id']}/entries")
        logs = api.get(f"api/v2/time/timesheets/{item['id']}/action-logs", params={"limit": 50})
        comparisons.append(
            {
                "list": {
                    "id": item["id"],
                    "employee": " ".join(
                        str(item["employee"].get(k))
                        for k in ("firstName", "middleName", "lastName")
                    ),
                    "middleName_raw": item["employee"].get("middleName"),
                    "terminationId": item["employee"].get("terminationId"),
                    "status": item["status"]["name"],
                    "period": [item["startDate"], item["endDate"]],
                },
                "detail_lookup": {
                    "id": default["id"],
                    "status": (default.get("status") or {}).get("name"),
                    "period": [default["startDate"], default["endDate"]],
                },
                "entries": {
                    "rows": len(entries["data"]),
                    "total": entries["meta"]["sum"]["label"],
                },
                "action_log": [
                    {
                        "action": lg["action"]["label"],
                        "date": lg["date"],
                        "by": " ".join(
                            filter(
                                None,
                                [
                                    (lg.get("performedEmployee") or {}).get("firstName"),
                                    (lg.get("performedEmployee") or {}).get("lastName"),
                                ],
                            )
                        ),
                    }
                    for lg in logs["data"]
                ],
                "same_timesheet": default["id"] == item["id"]
                and default["startDate"] == item["startDate"],
            }
        )
    DATA["time"] = {"pending_total": listing["meta"]["total"], "comparisons": comparisons}

    page.goto(f"{APP}/time/viewEmployeeTimesheet")
    wait_table(page)
    shot(page, "20_timesheets_pending_list")
    rows = page.locator(".oxd-table-body .oxd-table-card")
    DATA["time"]["ui_list_rows"] = [
        " | ".join(" ".join(c.split()) for c in r.locator(".oxd-table-cell").all_inner_texts())
        for r in rows.all()
    ]
    for index in range(min(rows.count(), 5)):
        page.goto(f"{APP}/time/viewEmployeeTimesheet")
        wait_table(page)
        highlight(page, ".oxd-table-body .oxd-table-card", index)
        shot(page, f"21_list_selected_{index + 1}", full=False)
        rows.nth(index).get_by_role("button", name="View").click()
        page.wait_for_url("**/viewTimesheet/**")
        page.locator(".orangehrm-timesheet-loader").wait_for(state="hidden")
        page.wait_for_timeout(1500)
        period = page.locator(".orangehrm-timeperiod-picker input").input_value()
        status = page.locator(".orangehrm-timesheet-footer--title").all_inner_texts()
        comparisons[index]["ui_detail"] = {"url": page.url, "period": period, "status": status}
        shot(page, f"22_detail_{index + 1}")


@step("Time: variações (reload, voltar/avançar, anterior/próximo, rede lenta)")
def timesheet_variations(page: Page, api: ApiClient) -> None:
    items = api.get("api/v2/time/employees/timesheets/list", params={"limit": 5})["data"]
    if not items:
        return
    item = items[0]
    emp, start = item["employee"]["empNumber"], item["startDate"]
    detail_url = f"{APP}/time/viewTimesheet/employeeId/{emp}?startDate={start}"
    period = page.locator(".orangehrm-timeperiod-picker input")
    loader = page.locator(".orangehrm-timesheet-loader")
    result: dict[str, Any] = {"item": item}

    page.goto(f"{APP}/time/viewEmployeeTimesheet")
    wait_table(page)
    page.goto(detail_url)
    loader.wait_for(state="hidden")
    page.wait_for_timeout(1200)
    result["initial"] = period.input_value()
    page.reload()
    loader.wait_for(state="hidden")
    page.wait_for_timeout(1200)
    result["after_reload"] = period.input_value()
    page.go_back()
    page.wait_for_timeout(1500)
    result["after_back_url"] = page.url
    page.go_forward()
    loader.wait_for(state="hidden")
    page.wait_for_timeout(1200)
    result["after_forward"] = period.input_value()

    page.locator(".orangehrm-timeperiod-icon.--prev").click()
    loader.wait_for(state="hidden")
    page.wait_for_timeout(1200)
    result["previous_period"] = period.input_value()
    result["previous_url"] = page.url
    shot(page, "23_detail_previous_period")
    page.locator(".orangehrm-timeperiod-icon.--next").click()
    loader.wait_for(state="hidden")
    page.wait_for_timeout(1200)
    result["back_to_period"] = period.input_value()

    page.goto(detail_url)
    loader.wait_for(state="hidden")
    page.wait_for_timeout(1200)
    held: list[Route] = []

    def hold(route: Route) -> None:
        if f"date={start}" in route.request.url:
            route.continue_()
        else:
            held.append(route)

    page.route("**/api/v2/time/timesheets/default?*", hold)
    page.locator(".orangehrm-timeperiod-icon.--prev").click()
    page.wait_for_timeout(150)
    page.locator(".orangehrm-timeperiod-icon.--next").click()
    page.wait_for_timeout(3000)
    result["slow_network_before_release"] = period.input_value()
    shot(page, "24_slow_network_before_release")
    for route in held:
        route.continue_()
    page.wait_for_timeout(3000)
    result["slow_network_after_release"] = period.input_value()
    result["slow_network_url"] = page.url
    result["slow_network_body"] = " ".join(
        page.locator(".orangehrm-paper-container").first.inner_text().split()
    )[:300]
    shot(page, "25_slow_network_after_release")
    page.unroute("**/api/v2/time/timesheets/default?*")
    DATA.setdefault("time", {})["variations"] = result


@step("Time: filtro por funcionário, My Timesheet, Dashboard e Attendance")
def time_integrations(page: Page, api: ApiClient) -> None:
    items = api.get("api/v2/time/employees/timesheets/list", params={"limit": 5})["data"]
    page.goto(f"{APP}/time/viewEmployeeTimesheet")
    wait_table(page)
    if items:
        emp = items[0]["employee"]
        field = page.locator(".oxd-autocomplete-text-input input").first
        field.fill(emp["firstName"])
        option = page.locator(".oxd-autocomplete-option", has_text=emp["lastName"]).first
        option.wait_for()
        option.click()
        shot(page, "26_filter_employee_selected", full=False)
        page.get_by_role("button", name="View").first.click()
        page.wait_for_url("**/viewTimesheet/**")
        page.locator(".orangehrm-timesheet-loader").wait_for(state="hidden")
        page.wait_for_timeout(1500)
        DATA.setdefault("time", {})["filter_view"] = {
            "url": page.url,
            "period": page.locator(".orangehrm-timeperiod-picker input").input_value(),
        }
        shot(page, "27_filter_employee_detail")

    page.goto(f"{APP}/time/viewMyTimesheet")
    page.locator(".orangehrm-timesheet-header").wait_for()
    page.wait_for_timeout(1500)
    shot(page, "28_my_timesheet")

    summary = api.get("api/v2/dashboard/employees/action-summary")["data"]
    DATA.setdefault("time", {})["dashboard_action_summary"] = summary
    page.goto(f"{APP}/dashboard/index")
    page.locator(".orangehrm-dashboard-widget").first.wait_for()
    page.wait_for_timeout(2500)
    widget = page.locator(".oxd-sheet.orangehrm-dashboard-widget", has_text="My Actions")
    DATA["time"]["dashboard_my_actions_text"] = " ".join(widget.inner_text().split())
    widget.screenshot(path=OUT / "29_dashboard_my_actions.png")

    page.goto(f"{APP}/attendance/viewAttendanceRecord")
    page.wait_for_timeout(2500)
    shot(page, "30_attendance_employee_records")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        request = p.request.new_context(timeout=SETTINGS.api_timeout_ms)
        api = ApiClient(request, SETTINGS)
        api.login(SETTINGS.admin_username, SETTINGS.admin_password.get_secret_value())
        state = OUT / "_state.json"
        request.storage_state(path=state)
        browser = p.chromium.launch()
        context = browser.new_context(
            storage_state=state,
            viewport={"width": 1440, "height": 900},
            locale=SETTINGS.locale,
            timezone_id=SETTINGS.timezone_id,
        )
        page = context.new_page()
        page.set_default_timeout(30_000)
        page.set_default_navigation_timeout(60_000)
        for collect in (
            environment,
            recruitment,
            hire_action_form,
            pim_directory,
            timesheets,
            timesheet_variations,
            time_integrations,
        ):
            collect(page, api)
        browser.close()
        state.unlink(missing_ok=True)
    (OUT / "data.json").write_text(json.dumps(DATA, indent=2, ensure_ascii=False), "utf-8")
    print(f"Evidências em {OUT} ({len(DATA['errors'])} etapa(s) com erro)")


if __name__ == "__main__":
    main()
