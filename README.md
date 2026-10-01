# OrangeHRM · Regressão automatizada do Recruitment

Suíte de regressão do módulo **Recruitment** do [OrangeHRM](https://opensource-demo.orangehrmlive.com/),
cobrindo a página pública de vagas, o formulário de candidatura e a consulta interna de candidatos.
Feita para rodar de novo por qualquer pessoa ou numa pipeline e apontar rápido quando uma mudança em
outra parte do sistema quebrar o fluxo de recrutamento.

| | |
|---|---|
| Linguagem | Python 3.11+ (CI em 3.12) |
| Navegador e HTTP | Playwright 1.56.0 (`pytest-playwright` 0.9.0) |
| Runner | pytest 9.1.1 + pytest-xdist (paralelo) |
| Configuração | pydantic-settings 2.14.2 (`.env` / variáveis `ORANGEHRM_*`) |
| Contratos de API | pydantic 2.13.4 |
| Relatório | Allure (allure-pytest 2.16.2, CLI 2.46.1) |
| Lint e formatação | Ruff 0.16.9 |
| CI/CD | GitHub Actions |
| Aplicação validada | OrangeHRM OS 5.9 (instância isolada) e demo pública |

## Por que este fluxo

O fluxo crítico escolhido é **vaga publicada → página pública → formulário de candidatura → candidato no
Recruitment**. É a única porta de entrada de candidatos externos: se a vaga não aparece, se o formulário
recusa um currículo válido ou aceita um inválido, ou se a candidatura não chega à consulta interna, o
recrutamento perde candidatos sem ninguém perceber. É também o ponto onde o suporte relata regressões
depois de mudanças em outras áreas (layout comum, validações compartilhadas, API).

## Arquitetura

```
src/orangehrm/
├── config/settings.py        # pydantic-settings: URL, credenciais, timeouts, trava de escrita
├── api/
│   ├── client.py             # cliente HTTP sobre APIRequestContext (login via CSRF, verbos)
│   ├── models.py             # contratos das respostas (pydantic)
│   └── recruitment.py        # serviços: API pública de vagas e API interna de Recruitment
├── pages/                    # Page Object Model
│   ├── base_page.py
│   ├── components/           # componentes oxd reutilizáveis (campo de formulário, tabela, diálogo)
│   ├── login_page.py
│   ├── public/               # página de vagas e formulário de candidatura
│   └── recruitment/          # Candidates
├── data/                     # dados sintéticos (candidatos e arquivos de currículo gerados em runtime)
└── support/                  # ambiente do Allure e seed do ambiente isolado
tests/
├── api/                      # contrato e regras da API pública
├── ui/                       # página de vagas, formulário, Candidates, login
└── e2e/                      # fluxo completo que grava dados (somente ambiente isolado)
infra/                        # OrangeHRM descartável via Docker Compose + seed
```

Decisões principais:

- **API first.** A API é a fonte de verdade e o atalho de preparação. O login é feito uma vez por
  sessão via HTTP e o `storage_state` é injetado no navegador; os testes de UI comparam a tela com a
  resposta da API (inclusive capturando a resposta que a própria tela consumiu, para não haver corrida
  com outros usuários da demo). Massa e limpeza dos cenários de escrita também são via API.
- **Page Objects sem asserções.** Páginas expõem ações e estado observável; o teste decide o que é
  certo. Locators priorizam atributos estáveis (`name`, papéis ARIA, texto visível) e componentes oxd
  ficam encapsulados em `pages/components`.
- **Regras vindas da aplicação, não inventadas.** Mensagens, limites (30/250 caracteres, 1 MB, tipos
  aceitos) e regras (apenas vagas ativas e publicadas, ordenação por id) são os exibidos pela tela ou
  definidos no código do OrangeHRM 5.9.
- **Ambiente compartilhado protegido.** Cenários que gravam têm o marcador `write` e só rodam com
  `ORANGEHRM_ALLOW_WRITE=true`; o `Settings` recusa essa flag quando a URL é a demo pública. Nos
  cenários negativos, um espião de rede prova que nenhuma candidatura foi enviada. No cenário positivo
  contra a demo, o envio é interceptado e abortado depois de validado o payload.

## Cenários

| Arquivo | Tipo | O que garante |
|---|---|---|
| `tests/api/test_public_vacancies_api.py` | API | Contrato da lista e do detalhe; só vagas ativas e publicadas; ordenação; paginação sem perdas; 404 para vaga inexistente; formulário responde 400 para vaga inexistente; lista de candidatos exige autenticação (401) |
| `tests/ui/test_job_board.py` | UI | Página pública mostra as vagas da API na mesma ordem; paginação cobre todas; Apply abre o formulário da vaga certa; Back volta à lista |
| `tests/ui/test_apply_form.py` | UI (negativo e limite) | Obrigatórios; só espaços; e-mail inválido (5 formatos); `.png` recusado; 1 MB + 1 byte recusado; arquivo vazio recusado; limites de 30/250 caracteres; telefone com letras. Nenhum envia dados |
| `tests/ui/test_apply_form.py` | UI (positivo) | Exatamente 1 MB aceito; as 6 extensões anunciadas aceitas; candidatura válida enviada com todos os campos, CSRF e arquivo (envio interceptado) |
| `tests/ui/test_candidates.py` | UI (somente leitura) | Lista de candidatos igual à resposta da API; filtro por nome encontra o candidato; estado vazio |
| `tests/ui/test_login.py` | UI | Login válido abre o Dashboard; senha inválida exibe "Invalid credentials" |
| `tests/e2e/test_apply_end_to_end.py` | E2E (`write`) | Candidatura pública cria candidato com os dados enviados, status "Application Initiated", histórico "Applied" e aparece em Candidates; sem consentimento grava `consentToKeepData=false`; vaga despublicada some da página e o formulário deixa de abrir |

Marcadores: `smoke`, `api`, `ui`, `e2e`, `write`.

## Como executar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install --with-deps chromium
cp .env.example .env            # opcional: padrão é a demo pública
```

Contra a demo pública (somente leitura; os cenários `write` são pulados):

```bash
pytest -n 4                     # suíte completa de leitura
pytest -m smoke                 # caminho crítico
pytest --headed -k apply_form   # ver o navegador
```

Contra um ambiente isolado (suíte completa, incluindo escrita com limpeza):

```bash
./infra/setup.sh                                   # sobe OrangeHRM 5.9 + MariaDB e popula massa
export ORANGEHRM_BASE_URL=http://localhost:8080
pytest -m "not write" -n auto                      # leitura em paralelo
ORANGEHRM_ALLOW_WRITE=true pytest -m write         # escrita, em série
./infra/teardown.sh                                # descarta tudo
```

Os cenários de escrita rodam em série e separados da leitura porque criam e removem vagas: em paralelo,
um teste de leitura poderia ver uma vaga que outro teste está excluindo.

Relatório:

```bash
allure serve reports/allure-results     # ou: allure generate ... --single-file
```

O relatório traz passos de negócio, prints de cada cenário, a resposta da API usada nas comparações,
categorias de falha e um `environment.properties` com URL, **versão do OrangeHRM detectada**, navegador,
versões e data da execução. Em falhas, ficam screenshot, vídeo e trace do Playwright em
`reports/test-results` (`playwright show-trace <arquivo>`).

## Ambiente isolado e estratégia de limpeza

`infra/docker-compose.yml` sobe a imagem oficial `orangehrm/orangehrm:5.9` com MariaDB em `tmpfs`
(nada persiste). `infra/setup.sh` instala pelo instalador CLI, desliga a exigência de senha forte para
usar as mesmas credenciais da demo (`Admin`/`admin123`) e roda `orangehrm.support.seed`, que cria 10
vagas (duas páginas na página pública) e 10 candidatos sintéticos.

Cada cenário de escrita cria a própria massa via API com sufixo único (cargo e vaga) e, no teardown,
remove via API tudo o que criou, mesmo se falhar: candidatos da vaga → vaga → cargo. No CI a instância
inteira é descartada ao fim.

## CI/CD

`.github/workflows/ci.yml`:

1. **Ruff**: `ruff check` e `ruff format --check`.
2. **Regressão completa (ambiente isolado)**: sobe o OrangeHRM em Docker, roda leitura em paralelo e
   escrita em série, descarta o ambiente. É o gate de PR.
3. **Regressão de leitura (demo pública)**: mesma suíte de leitura contra a demo, também agendada em
   dias úteis às 06:00 (BRT) para detectar mudanças na demo. Usa uma nova tentativa (`--reruns 1`) por
   ser um ambiente compartilhado e instável; o Allure mostra quais testes precisaram dela.

Cada execução publica como artefatos o relatório Allure em arquivo único (`allure-report-*`), os
resultados brutos e os traces de falha.

## Dados sintéticos

Nomes fictícios (`Qa Auto Candidate<sufixo>`), e-mails no domínio reservado `example.com` (RFC 2606),
telefone genérico e currículos gerados em tempo de execução (`src/orangehrm/data`). Nenhum dado pessoal
real, credencial corporativa ou arquivo real é usado. As credenciais padrão são as públicas da demo.

## Limitações conhecidas

- **A demo pública é compartilhada e muda.** Vagas e candidatos são criados e apagados por outras
  pessoas; por isso os testes de leitura derivam o esperado da API no momento do teste e pulam (com
  motivo) quando falta massa. Na demo, o envio real de candidatura não é feito.
- **Versão.** Validado em OrangeHRM OS 5.9. A versão da demo é registrada em cada relatório; seletores
  dependem dos componentes oxd e podem exigir ajuste em versões futuras.
- **Validação de arquivo é por MIME type do navegador.** O cliente aceita o arquivo pelo tipo que o
  navegador informa (derivado da extensão), não pelo conteúdo.
- **Arquivo vazio** é recusado com a mensagem "Attachment Size Exceeded" (a regra de tamanho trata 0
  byte como inválido), o que é enganoso para o usuário. O teste valida a recusa, não a mensagem.
- **Busca por nome em Candidates** sugere candidatos por primeiro, meio *ou* último nome
  separadamente; digitar o nome completo não traz sugestões. O Page Object digita uma parte do nome.
- **Validação do servidor** do envio público não é exercitada diretamente na demo (exigiria gravar);
  fica coberta pelo E2E no ambiente isolado.

## Como a suíte pode crescer

- Novos módulos ganham seus serviços em `api/` e páginas em `pages/` reaproveitando os componentes.
- Mais navegadores: `pytest --browser firefox --browser webkit` (ou matriz no workflow).
- Contratos da API podem virar testes de contrato versionados (snapshot do schema JSON).
- Acessibilidade com `axe-core` nas páginas públicas e testes visuais do formulário.
- Histórico de tendência no Allure publicando o relatório no GitHub Pages.
