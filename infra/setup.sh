#!/usr/bin/env bash
# Sobe uma instância isolada do OrangeHRM, instala, iguala as credenciais às da
# demo pública (Admin/admin123) e popula massa sintética para a regressão.
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE="docker compose -f docker-compose.yml"
PORT="${ORANGEHRM_PORT:-8080}"
BASE="http://localhost:${PORT}"

echo ">> Subindo containers"
$COMPOSE up -d --wait db
$COMPOSE up -d app

echo ">> Instalando OrangeHRM (instalador CLI)"
$COMPOSE exec -T app bash -c '
  cp /opt/qa/install-config.yaml installer/cli_install_config.yaml &&
  php installer/cli_install.php'

echo ">> Desligando a exigência de senha forte (a demo pública usa admin123)"
$COMPOSE exec -T db mariadb -uroot -proot orangehrm_qa -e \
  "UPDATE hs_hr_config SET value='off' WHERE name='auth.password_policy.enforce_password_strength';"

echo ">> Aguardando ${BASE}"
for _ in $(seq 1 60); do
  if curl -fsS "${BASE}/web/index.php/auth/login" >/dev/null; then break; fi
  sleep 2
done

echo ">> Populando massa sintética"
ORANGEHRM_BASE_URL="${BASE}" ORANGEHRM_ALLOW_WRITE=true \
  python -m orangehrm.support.seed

echo ">> Ambiente pronto em ${BASE}"
