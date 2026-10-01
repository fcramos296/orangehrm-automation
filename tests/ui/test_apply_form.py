"""Formulário público de candidatura: validações e envio.

Todos os cenários deste arquivo são seguros para o ambiente compartilhado:
- negativos/limite: a validação do cliente bloqueia o envio, e o teste prova
  que nenhuma requisição de candidatura saiu do navegador;
- positivo: o envio é interceptado na rede e abortado depois de validado o
  payload, então nada é gravado. O envio real fica em tests/e2e (ambiente isolado).

Mensagens e limites esperados são os exibidos pela própria aplicação
(rótulos, dica "up to 1MB" e regras de validação do componente).
"""

from __future__ import annotations

from pathlib import Path

import allure
import pytest
from playwright.sync_api import Request, Route, expect

from orangehrm.data import files
from orangehrm.data.applicants import build_applicant
from orangehrm.pages.public.apply_vacancy_page import SUBMIT_ENDPOINT_GLOB, ApplyVacancyPage

pytestmark = [pytest.mark.ui, allure.feature("Recruitment - Formulário de candidatura")]

REQUIRED = "Required"
INVALID_EMAIL = "Expected format: admin@example.com"
TYPE_NOT_ALLOWED = "File type not allowed"
SIZE_EXCEEDED = "Attachment Size Exceeded"
INVALID_PHONE = "Allows numbers and only + - / ( )"


def assert_nothing_submitted(spy) -> None:
    assert not spy.requests, "A candidatura foi enviada apesar do formulário inválido"


# --- negativos -----------------------------------------------------------------


@pytest.mark.smoke
@allure.story("Campos obrigatórios")
@allure.title("Envio vazio aponta todos os campos obrigatórios e não envia a candidatura")
def test_required_fields(apply_form: ApplyVacancyPage, submission_spy):
    apply_form.submit()

    expect(apply_form.errors).to_have_count(4)
    assert apply_form.error_messages() == {
        "firstName": REQUIRED,
        "lastName": REQUIRED,
        "email": REQUIRED,
        "resume": REQUIRED,
    }
    apply_form.attach_screenshot("Campos obrigatórios")
    assert_nothing_submitted(submission_spy)


@allure.story("Campos obrigatórios")
@allure.title("Campo obrigatório preenchido só com espaços é recusado: {field}")
@pytest.mark.parametrize("field", ["firstName", "lastName", "email"])
def test_whitespace_only_is_required(apply_form: ApplyVacancyPage, submission_spy, field, tmp_path):
    apply_form.fill_applicant(build_applicant())
    apply_form.upload_resume(files.text_resume(tmp_path))
    apply_form.field(field).fill("   ")

    apply_form.submit()

    assert apply_form.error_messages() == {field: REQUIRED}
    assert_nothing_submitted(submission_spy)


@allure.story("E-mail")
@allure.title("E-mail em formato inválido é recusado: '{email}'")
@pytest.mark.parametrize(
    "email",
    ["candidato", "candidato@", "@example.com", "candidato@example", "candidato @example.com"],
)
def test_invalid_email(apply_form: ApplyVacancyPage, submission_spy, email, tmp_path):
    apply_form.fill_applicant(build_applicant(email=email))
    apply_form.upload_resume(files.text_resume(tmp_path))

    apply_form.submit()

    assert apply_form.error_messages() == {"email": INVALID_EMAIL}
    assert_nothing_submitted(submission_spy)


@allure.story("Currículo")
@allure.title("Extensão não permitida é recusada (.png)")
def test_resume_type_not_allowed(apply_form: ApplyVacancyPage, submission_spy, tmp_path):
    apply_form.fill_applicant(build_applicant())
    apply_form.upload_resume(files.image_file(tmp_path))

    apply_form.submit()

    assert apply_form.error_messages() == {"resume": TYPE_NOT_ALLOWED}
    apply_form.attach_screenshot("Tipo de arquivo não permitido")
    assert_nothing_submitted(submission_spy)


@allure.story("Currículo")
@allure.title("Currículo 1 byte acima de 1 MB é recusado")
def test_resume_above_size_limit(apply_form: ApplyVacancyPage, submission_spy, tmp_path):
    apply_form.fill_applicant(build_applicant())
    apply_form.upload_resume(files.pdf_resume(tmp_path, size=files.MAX_RESUME_BYTES + 1))

    apply_form.submit()

    assert apply_form.error_messages() == {"resume": SIZE_EXCEEDED}
    apply_form.attach_screenshot("Arquivo acima do limite")
    assert_nothing_submitted(submission_spy)


@allure.story("Currículo")
@allure.title("Currículo vazio (0 byte) é recusado")
def test_empty_resume_is_rejected(apply_form: ApplyVacancyPage, submission_spy, tmp_path):
    apply_form.fill_applicant(build_applicant())
    apply_form.upload_resume(files.empty_file(tmp_path))

    apply_form.submit()

    # A aplicação recusa, mas reaproveita a mensagem de tamanho excedido
    # (regra maxFileSize trata size 0 como inválido). Registrado nas limitações.
    assert "resume" in apply_form.error_messages()
    assert_nothing_submitted(submission_spy)


@allure.story("Limites de texto")
@allure.title("Limite de caracteres: {field} aceita {limit} e recusa {limit}+1")
@pytest.mark.parametrize(
    ("field", "limit"),
    [("firstName", 30), ("middleName", 30), ("lastName", 30), ("keywords", 250), ("comment", 250)],
)
def test_text_length_boundaries(apply_form: ApplyVacancyPage, field, limit):
    target = apply_form.field(field)

    target.fill("a" * limit)
    assert target.error_text() is None

    target.fill("a" * (limit + 1))
    assert target.error_text() == f"Should not exceed {limit} characters"


@allure.story("Telefone")
@allure.title("Telefone com letras é recusado")
def test_invalid_contact_number(apply_form: ApplyVacancyPage, submission_spy, tmp_path):
    apply_form.fill_applicant(build_applicant(contact_number="51 9999-ABCD"))
    apply_form.upload_resume(files.text_resume(tmp_path))

    apply_form.submit()

    assert apply_form.error_messages() == {"contactNumber": INVALID_PHONE}
    assert_nothing_submitted(submission_spy)


# --- positivos -----------------------------------------------------------------


@allure.story("Currículo")
@allure.title("Currículo com exatamente 1 MB é aceito")
def test_resume_at_size_limit_is_accepted(apply_form: ApplyVacancyPage, tmp_path):
    apply_form.upload_resume(files.pdf_resume(tmp_path, size=files.MAX_RESUME_BYTES))

    assert apply_form.field("resume").error_text() is None


@allure.story("Currículo")
@allure.title("Extensão anunciada como aceita passa na validação: {extension}")
@pytest.mark.parametrize("extension", files.ALLOWED_EXTENSIONS)
def test_allowed_resume_extensions(apply_form: ApplyVacancyPage, extension, tmp_path):
    resume = tmp_path / f"curriculo{extension}"
    resume.write_bytes(b"Curriculo sintetico")

    apply_form.upload_resume(resume)

    assert apply_form.field("resume").error_text() is None


@pytest.mark.smoke
@allure.story("Envio")
@allure.title("Candidatura válida é enviada com todos os dados (envio interceptado, sem gravar)")
def test_valid_application_payload(apply_form: ApplyVacancyPage, target_vacancy, tmp_path: Path):
    applicant = build_applicant()
    resume = files.pdf_resume(tmp_path)
    captured: list[Request] = []

    def intercept(route: Route) -> None:
        captured.append(route.request)
        route.abort()  # nada chega ao servidor compartilhado

    apply_form.page.route(SUBMIT_ENDPOINT_GLOB, intercept)
    apply_form.fill_applicant(applicant)
    apply_form.upload_resume(resume)
    apply_form.attach_screenshot("Formulário válido preenchido")
    assert apply_form.error_messages() == {}

    with apply_form.page.expect_event("requestfailed"):
        apply_form.submit()

    assert len(captured) == 1, "Envio deveria gerar exatamente uma requisição"
    request = captured[0]
    body = request.post_data_buffer or b""
    assert request.method == "POST"
    assert "multipart/form-data" in (request.headers.get("content-type") or "")
    expected_fields = {
        "vacancyId": str(target_vacancy.id),
        "firstName": applicant.first_name,
        "middleName": applicant.middle_name,
        "lastName": applicant.last_name,
        "email": applicant.email,
        "contactNumber": applicant.contact_number,
        "keywords": applicant.keywords,
        "comment": applicant.notes,
        "consentToKeepData": "on",
    }
    with allure.step("Conferir campos do multipart enviado"):
        for name, value in expected_fields.items():
            part = f'name="{name}"\r\n\r\n{value}\r\n'.encode()
            assert part in body, f"Campo {name}={value!r} ausente no envio"
        assert b'name="_token"' in body, "CSRF token não enviado"
        assert f'filename="{resume.name}"'.encode() in body
