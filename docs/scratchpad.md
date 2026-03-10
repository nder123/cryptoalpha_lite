# Бортовой журнал команды CryptoAlpha

## Текущий план
(Здесь Планировщик будет писать план)

## Прогресс выполнения
- [2026-02-25T15:48:56] codex: задача 'тест notify: пинг' -> /home/ander/CascadeProjects/cryptoalpha_lite/backend/.codex_out/2026-02-25T15-48-56_7705797237b2.md
- [2026-02-25T15:48:57] codex: задача 'тест notify: пинг' -> /home/ander/CascadeProjects/cryptoalpha_lite/backend/.codex_out/2026-02-25T15-48-57_7705797237b2.md
- [2026-02-25T15:35:50] codex: задача 'тест codex: напиши короткий план как проверить /api/health' -> /home/ander/CascadeProjects/cryptoalpha_lite/backend/.codex_out/2026-02-25T15-35-50_024e115cd383.md
- [2026-02-25T15:32:29] codex: задача 'тест codex: напиши короткий план как проверить /api/health' -> /home/ander/CascadeProjects/cryptoalpha_lite/backend/.codex_out/2026-02-25T15-32-29_024e115cd383.md
- [2026-02-25T15:29:57] codex: задача 'тест codex: напиши короткий план как проверить /api/health' -> /home/ander/CascadeProjects/cryptoalpha_lite/backend/.codex_out/2026-02-25T15-29-57_024e115cd383.md
- [2026-02-25T15:28:44] codex: задача 'тест codex: напиши короткий план как проверить /api/health' -> /home/ander/CascadeProjects/cryptoalpha_lite/backend/.codex_out/2026-02-25T15-28-44_024e115cd383.md
- [2026-03-07] recommender: поднят `--primary-epsilon-a` с `0.002` до `0.0022` в `~/.config/systemd/user/cryptoalpha-recommender.service`
  - Зачем: избежать ложного провала окна A по primary из-за микрошагов/округления (например `dd=-0.0048` vs порог `-0.0047`).
  - Как проверить:
    - `systemctl --user daemon-reload && systemctl --user restart cryptoalpha-recommender.service`
    - `journalctl --user -u cryptoalpha-recommender.service --since "5 minutes ago" --no-pager | tail -n 80`

- [2026-03-07] recommender: добавлены строгие event-строки в journald для суточной проверки
  - Что: `backend/scripts/rl_promotion_recommender.py` теперь печатает отдельные строки:
    - `new_policy_version ...`
    - `NOT_RECOMMENDED ...`
    - `PROMOTE_RECOMMENDED ...`
  - Зачем: чтобы можно было 1 раз в сутки надёжно грепать события, не парся `recommender_status`.
  - Как проверить:
    - `systemctl --user restart cryptoalpha-recommender.service`
    - `journalctl --user -u cryptoalpha-recommender.service --since "30 hours ago" --no-pager | grep -E "PROMOTE_RECOMMENDED|NOT_RECOMMENDED|new_policy_version" | tail -n 50`

- [2026-03-07] alias для суточной проверки событий recommender (zsh)
  - Добавить в `~/.zshrc`:
    - `alias rlp='journalctl --user -u cryptoalpha-recommender.service --since "30 hours ago" --no-pager | grep -E "PROMOTE_RECOMMENDED|NOT_RECOMMENDED|new_policy_version" | tail -n 200'`
  - Использование: 1 раз в сутки запускать `rlp` и смотреть, было ли `PROMOTE_RECOMMENDED`.

- [2026-03-09] recommender: как не попасть на старые PROMOTE_RECOMMENDED в journald
  - Проблема: `journalctl --since "30 hours ago"` показывает исторические рекомендации, которые могли быть до фиксов (например до внедрения `PROMOTE_NOT_ACTIONABLE`).
  - Решение: смотреть события в коротком окне или от конкретного времени.
  - Пример (последние 6 часов):
    - `journalctl --user -u cryptoalpha-recommender.service --since "6 hours ago" --no-pager | grep -E "PROMOTE_RECOMMENDED|PROMOTE_NOT_ACTIONABLE|NOT_RECOMMENDED|new_policy_version" | tail -n 200`
  - Пример (строго от времени):
    - `journalctl --user -u cryptoalpha-recommender.service --since "2026-03-08 09:30" --no-pager | grep -E "PROMOTE_RECOMMENDED|PROMOTE_NOT_ACTIONABLE|NOT_RECOMMENDED|new_policy_version" | tail -n 200`

- [2026-03-10] ops: operator-friendly RL recommender signals через systemd/journald
  - Что:
    - `cryptoalpha-recommender-events.timer` -> `cryptoalpha-recommender-events.service` (digest каждые ~5 минут)
      - печатает последние `PROMOTE_RECOMMENDED|NOT_RECOMMENDED|ROLLBACK_RECOMMENDED` за окно
      - если событий нет: пишет `no recommender events in window`
    - `cryptoalpha-recommender-alerts.timer` -> `cryptoalpha-recommender-alerts.service` (критичные алерты)
      - если найдено `PROMOTE_RECOMMENDED|ROLLBACK_RECOMMENDED`, пишет в journald с тэгом `cryptoalpha-rl-alert` и priority `alert`
  - Как смотреть:
    - Digest:
      - `journalctl --user -u cryptoalpha-recommender-events.service -n 200 --no-pager --output=cat`
    - ALERT-поток (то, что нельзя пропустить):
      - `journalctl --user -t cryptoalpha-rl-alert -p alert -n 50 --no-pager --output=cat`
    - Таймеры:
      - `systemctl --user list-timers --all --no-pager | grep -E "cryptoalpha-recommender-(events|alerts)"`

- [2026-03-08] RL manual promote: добавлено хранение policy по версиям + переключение активной версии (для ручного promote)
  - Что:
    - `backend/app/services/rl_trainer.py`
      - сохраняет payload policy в Redis по ключу `rl_policy:by_version:<version>`
      - как и раньше обновляет `rl_policy:latest`
      - один раз (если нет) выставляет `rl_policy:active_version=<version>`
    - `backend/app/services/rl_policy.py`
      - evaluator читает активную policy по `rl_policy:active_version` (из `rl_policy:by_version:<version>`)
      - fallback на `rl_policy:latest`, если активная версия не найдена
    - `backend/app/api/routes.py`
      - `POST /api/rl/policy/promote` — ручной promote: установить `rl_policy:active_version=<version>` (только если версия существует)
      - `GET /api/rl/status` теперь возвращает `active_policy_version` и `active_policy`
    - `backend/scripts/rl_status.py`
      - теперь показывает `active_policy_version` и `active_policy`
    - `backend/scripts/rl_promotion_recommender.py`
      - в `PROMOTE_RECOMMENDED` добавлена готовая команда `curl` для ручного promote
  - Зачем: без этого `rl_policy:latest` перезаписывается при каждом retrain и нельзя безопасно «промоутить» конкретную policy_version по событию.
  - Как проверить:
    - дождаться следующего обучения (чтобы появилась запись `rl_policy:by_version:<version>`)
    - `curl -s http://127.0.0.1:8000/api/rl/status | grep -E 'active_policy_version|active_policy|policy' -n -A3`
    - выполнить ручной promote:
      - `curl -s -X POST http://127.0.0.1:8000/api/rl/policy/promote -H 'Content-Type: application/json' -d '{"version":"<version>"}'`
    - ещё раз проверить `/api/rl/status`:
      - ожидаемо: `active_policy_version == <version>` и `active_policy.version == <version>`

- [2026-03-08] recommender: PROMOTE_RECOMMENDED только для promotable версий
  - Что:
    - backend: добавлен read-only endpoint `GET /api/rl/policy/exists?version=...` (проверяет наличие в `rl_policy:by_version:*` или совпадение с `rl_policy:latest`)
    - recommender: перед `PROMOTE_RECOMMENDED` проверяет promotable; если версия не promotable, пишет `PROMOTE_NOT_ACTIONABLE` (ждать следующую policy_version)
  - Зачем: чтобы не рекомендовать промоут для старых версий, которые были обучены до введения `rl_policy:by_version:*` и не могут быть активированы.

- [2026-03-08] dev/qa helpers: добавлены быстрые гейты качества и CI (без ожиданий)
  - Что:
    - добавлен `/.pre-commit-config.yaml` (ruff/black/isort/bandit + базовые хуки)
    - добавлен `/.github/workflows/ci.yml`:
      - quality job: **RL-only** (ruff/black/isort/bandit) + bandit без блокировки на шумные правила для внутренних RL-скриптов
      - tests job: `pytest` + coverage
    - добавлены `.windsurf/workflows/*`:
      - `local-quality.md`
      - `ci-quality-gates.md`
      - `code-review.md`
      - `release-staging.md`
    - `backend/pyproject.toml`: dev deps `pre-commit`, `bandit`, `pytest-cov` (и временно `mypy`, но mypy-гейт отключён в CI)
  - Зачем:
    - чтобы проверки были воспроизводимы и запускались быстро, без массового форматирования всего backend.
  - Как проверить:
    - `cd backend && poetry run pytest -q`
    - `cd backend && poetry run ruff check app/services/rl_*.py scripts/rl_promotion_recommender.py scripts/rl_status.py scripts/rl_snapshots_collect.py scripts/rl_snapshots_report.py scripts/rl_baseline_watchdog.py scripts/rl_baseline_helper.py`

- [2026-03-08] tests: починен unit-тест `tests/test_full_cycle.py`
  - Что:
    - добавлено обязательное поле `action` в `ExecutionReport` (OPEN/CLOSE)
    - добавлен `_remember_directive(close_directive)` перед обработкой close-report
  - Результат:
    - `poetry run pytest -q` -> `4 passed`

- [2026-03-08] smoke: проверка что система не сломалась
  - Что проверено:
    - `curl -fsS http://127.0.0.1:8000/api/health` -> `{"status":"ok"}`
    - `curl -fsS http://127.0.0.1:8000/api/rl/status` -> валидный JSON
    - `systemctl --user is-active cryptoalpha-backend.service cryptoalpha-recommender.service cryptoalpha-snapshots.service` -> `active`
    - unit-тесты зелёные

## Периодические проверки (запускать когда нужно)

- После любых изменений в backend/RL (или перед рестартом сервисов):
  - `cd backend && poetry run pytest -q`

- Daily monitoring routine (1 раз в день / после retrain / после promote):
  - API smoke:
    - `curl -fsS http://127.0.0.1:8000/api/health >/dev/null && echo OK_health`
    - `curl -fsS http://127.0.0.1:8000/api/rl/status | head -c 600; echo`
    - `curl -fsS http://127.0.0.1:8000/api/config/runtime | grep -E 'rl_enabled|rl_autopilot_enabled|max_symbol_allocation_pct|max_portfolio_exposure_usdt'`
  - Recommender events (за последние 30ч):
    - `journalctl --user -u cryptoalpha-recommender.service --since "30 hours ago" --no-pager | grep -E "PROMOTE_RECOMMENDED|PROMOTE_NOT_ACTIONABLE|NOT_RECOMMENDED|new_policy_version" | tail -n 200`
  - Backend RL usage (логи в journald):
    - `journalctl --user -u cryptoalpha-backend.service --since "30 hours ago" --no-pager | grep -E 'rl_trainer_policy_loaded|rl_policy_loaded|directive_adjusted_by_rl' | tail -n 200`
  - Быстрая сверка: backend грузит именно `active_policy_version`:
    - `v=$(curl -fsS http://127.0.0.1:8000/api/rl/status | python -c 'import json,sys; print(json.load(sys.stdin).get("active_policy_version") or "")'); echo "active_policy_version=$v"; journalctl --user -u cryptoalpha-backend.service --since "30 hours ago" --no-pager | grep -F "rl_policy:by_version:$v" | tail -n 5`

- Ежедневно (или после retrain) проверять события recommender:
  - `journalctl --user -u cryptoalpha-recommender.service --since "30 hours ago" --no-pager | grep -E "PROMOTE_RECOMMENDED|PROMOTE_NOT_ACTIONABLE|NOT_RECOMMENDED|new_policy_version" | tail -n 200`

- После рестарта backend / при подозрении на проблемы:
  - `curl -fsS http://127.0.0.1:8000/api/health`
  - `curl -fsS http://127.0.0.1:8000/api/rl/status | head -c 600; echo`
  - `GET /api/rl/policy/exists` expects `version` as a query param; the value contains `+00:00` which must be URL-encoded in the query string (otherwise `+` becomes a space and `exists` may return false for a valid version). Use:
    - `curl -sG "http://127.0.0.1:8000/api/rl/policy/exists" --data-urlencode "version=<VERSION>"`

- Шум в логах recommender:
  - После успешного ручного promote recommender больше не должен повторно эмитить `PROMOTE_RECOMMENDED` для версии, которая уже стала `active_policy_version` (берётся из `/api/rl/status`).

- Быстрый RL-checklist одной командой (pytest + RL-quality + smoke):
  - `bash -lc 'set -euo pipefail; cd /home/ander/CascadeProjects/cryptoalpha_lite/backend; poetry run pytest -q; poetry run ruff check app/services/rl_*.py scripts/rl_promotion_recommender.py scripts/rl_status.py scripts/rl_snapshots_collect.py scripts/rl_snapshots_report.py scripts/rl_baseline_watchdog.py scripts/rl_baseline_helper.py; poetry run black --check app/services/rl_*.py scripts/rl_promotion_recommender.py scripts/rl_status.py scripts/rl_snapshots_collect.py scripts/rl_snapshots_report.py scripts/rl_baseline_watchdog.py scripts/rl_baseline_helper.py; poetry run isort --check-only app/services/rl_*.py scripts/rl_promotion_recommender.py scripts/rl_status.py scripts/rl_snapshots_collect.py scripts/rl_snapshots_report.py scripts/rl_baseline_watchdog.py scripts/rl_baseline_helper.py; poetry run bandit -q -s B101,B112,B310,B404,B603,B607 app/services/rl_*.py scripts/rl_promotion_recommender.py scripts/rl_status.py scripts/rl_snapshots_collect.py scripts/rl_snapshots_report.py scripts/rl_baseline_watchdog.py scripts/rl_baseline_helper.py; curl -fsS http://127.0.0.1:8000/api/health >/dev/null; curl -fsS http://127.0.0.1:8000/api/rl/status >/dev/null; echo OK'
(Здесь Кодер будет отмечать, что сделано)

## Git / GitHub (bootstrap)

- Репозиторий ведём только в `/home/ander/CascadeProjects/cryptoalpha_lite`.
- pre-commit стабилизирован: `poetry run pre-commit run -a` должен проходить без модификаций файлов.
- Runtime-артефакты/логи не коммитим (см. `.gitignore`; из индекса убраны `backend/.codex_out/*`, `frontend/.vite.*`).

- GitHub repo:
  - `https://github.com/andersen-123/cryptoalpha_lite`
  - `origin` (SSH): `git@github.com:andersen-123/cryptoalpha_lite.git`

- SSH setup (если после нового терминала снова спрашивает passphrase):
  - `eval "$(ssh-agent -s)"`
  - `ssh-add ~/.ssh/id_ed25519`
  - `ssh -T git@github.com` -> `Hi andersen-123! ...`

- Основные git-команды (обычный цикл):
  - `git status -sb`
  - `git pull --rebase`
  - `poetry run pre-commit run -a`
  - `git add -A && git commit -m "..."`
  - `git push`

- Важно:
  - Если когда-либо был засвечен GitHub PAT (строка вида `ghp_...`) — его нужно отозвать в GitHub Settings -> Developer settings -> Personal access tokens.

## Задачи для параллельного выполнения
(Здесь Планировщик отмечает задачи, которые можно делегировать Codex CLI)
- [x] тест настроить автопроверку работоспособности каждые 20 минут: `crontab -e` и добавить строку `*/20 * * * * curl http://localhost:8000/api/health`
- [x] что сейчас происходит с системой
- [x] тест codex: напиши короткий план как проверить /api/health
- [x] тест notify: пинг
## Прогресс выполнения
- Проверка работоспособности выполнена (24 фев 2026):
  - API: `/api/health` и `/api/rl/status` отвечают `200`.
  - RL метрики обновляются (timestamp свежий), `total_trades` растёт.
  - Стримы событий живые: `positions/execution/hypotheses/risk` возвращают свежие события.
  - Сбор снапшотов работает: `rl_snapshots_collect.py` запущен, `rl_status_snapshots.jsonl` обновляется.
  - В хвосте `.uvicorn.log` свежих ошибок не найдено.

- Автопроверка `/api/health` каждые 20 минут настроена через `crontab`:
  - `*/20 * * * * curl -fsS http://localhost:8000/api/health >> /home/ander/CascadeProjects/cryptoalpha_lite/backend/.health_cron.log 2>&1`

## Текущий план
- Мониторить версии политик в since-окне (от TS_RESTART_V2) до набора достаточной статистики.
- Сравнивать версии только при `>=72` трейдах на версию и подтверждать лидерство в 2 окнах подряд.
## Статус тестов
(Здесь Контролёр будет писать, запущены ли тесты CTO AI и их результаты)

## Важно для системы
- ОЗУ: 7.7 ГБ + своп 14 ГБ
- Тесты CTO AI: **ЗАПУЩЕНЫ** (не останавливать!)
- Codex CLI: доступен в терминале Manjaro

## Инвентаризация RL (кто за что отвечает)

### Сервисы systemd (user)
- `cryptoalpha-backend.service` — backend API (uvicorn). Даёт `/api/rl/status`, принимает торговые события, хранит/обслуживает RL состояние.
- `cryptoalpha-snapshots.service` — периодически пишет снапшоты RL статуса в `backend/rl_status_snapshots.jsonl` (источник для отчётов/сравнений окон).
- `cryptoalpha-recommender.service` — промоушн-рекомендер: сравнивает policy_version по окнам A/B (через снапшоты), выдаёт события `PROMOTE_RECOMMENDED`/`NOT_RECOMMENDED` и desktop notify (не делает автопромоут).

### Скрипты backend/scripts
- `rl_snapshots_collect.py` — коллектор снапшотов (запускается `cryptoalpha-snapshots.service`).
- `rl_snapshots_report.py` — отчёты по снапшотам (режимы агрегации, сортировки, фильтры по окнам).
- `rl_promotion_recommender.py` — логика рекомендаций промоушна (состояние в `backend/.promotion_recommender_state.json`).
- `rl_status.py` — утилита просмотра/диагностики RL статуса.
- `rl_baseline_helper.py` / `rl_baseline_watchdog.py` — вспомогательные утилиты вокруг baseline/стабилизации (используются для поддержки режима сравнения в окне A).
- `rl_replay.py` — оффлайн/локальный реплей (для воспроизведения/диагностики).

### Компоненты backend/app/services
- `app/services/rl_trainer.py` — RL training loop: собирает опыт, считает награды, обучает, публикует метрики и сохраняет policy в Redis.
- `app/services/rl_policy.py` — загрузка policy из Redis и применение (оценка фич -> решение/скор).
- `app/services/rl_autopilot.py` — dry-run автопилот, генерирует OPEN/CLOSE циклы для накопления трейдов/опыта (включается runtime config флагами).

## RL promotion rules (current)

- В `/api/rl/status`:
  - `policy.version` = последняя обученная политика (redis key `rl_policy:latest`).
  - `active_policy_version` = промоутнутая политика (redis key `rl_policy:active_version`).
  - Норма: `policy.version` может отличаться от `active_policy_version`.
  - Инвариант: backend должен загружать именно `active_policy_version` (ключ `rl_policy:by_version:<active>`).

- Recommender (`cryptoalpha-recommender.service`) сравнивает версии по окнам через `rl_snapshots_report.py` (mode=trades).
  - Окно: `--hours 12`.
  - Eligibility: версия участвует в сравнении, если `trades >= --min-trades 72`.
  - Primary metric: `max_drawdown` (чем ближе к 0 / больше, тем лучше; значения обычно отрицательные).
  - Primary pass: `current_dd >= leader_dd - primary_epsilon`.
    - Сейчас для окна A: `--primary-epsilon-a 0.0022`.
  - Secondary floor: `p50_pnl_pct >= --secondary-floor` и `avg_pnl_pct >= --secondary-floor`.
    - Сейчас: `--secondary-floor -0.0002`.
  - Not recommended gap: если разница по primary хуже, чем `--not-recommended-gap`.
    - Сейчас: `--not-recommended-gap 0.005`.
  - Confirm streak: рекомендация `PROMOTE_RECOMMENDED` только после `--confirm-streak 2` окон подряд.
  - Проверка promotable (`/api/rl/policy/exists`) должна URL-энкодить `version` (символ `+` в `+00:00`), иначе `exists` может стать false.

## RL promote / rollback (operator workflow)

- Перед promote (зафиксировать точку отката):
  - `prev_active=$(curl -fsS http://127.0.0.1:8000/api/rl/status | python -c 'import json,sys; print(json.load(sys.stdin).get("active_policy_version") or "")'); echo "prev_active=$prev_active"`
  - Вставить строку `prev_active=<...>` в scratchpad (или в commit message), чтобы откат был быстрым.

- Promote latest -> active (ручной promote):
  - `latest=$(curl -fsS http://127.0.0.1:8000/api/rl/status | python -c 'import json,sys; print(((json.load(sys.stdin).get("policy") or {}).get("version")) or "")'); echo "latest=$latest"`
  - `curl -fsS -X POST http://127.0.0.1:8000/api/rl/policy/promote -H 'Content-Type: application/json' -d '{"version":"'$latest'"}' | python -m json.tool`

- Verify after promote:
  - `curl -fsS http://127.0.0.1:8000/api/rl/status | python -m json.tool | grep -E 'active_policy_version|"policy"|"active_policy"' -n | head -n 60`
  - `v=$(curl -fsS http://127.0.0.1:8000/api/rl/status | python -c 'import json,sys; print(json.load(sys.stdin).get("active_policy_version") or "")'); echo "active_policy_version=$v"; journalctl --user -u cryptoalpha-backend.service --since "30 minutes ago" --no-pager | grep -F "rl_policy:by_version:$v" | tail -n 5`

- Rollback (ручной):
  - Использовать сохранённый `prev_active=<...>` и выполнить promote на него:
    - `curl -fsS -X POST http://127.0.0.1:8000/api/rl/policy/promote -H 'Content-Type: application/json' -d '{"version":"<PREV_ACTIVE>"}' | python -m json.tool`
  - Затем повторить Verify (см. выше).
