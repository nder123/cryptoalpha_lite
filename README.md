# CryptoAlpha CTO-AI Platform

Полностью автономная платформа для торговли фьючерсами Bybit USDT-M с единой точкой принятия решений (CTO-AI), модульной архитектурой и веб-дэшбордом как единственной поверхностью управления.

## Обзор архитектуры
- **Backend**: FastAPI (REST + WebSocket), асинхронные сервисы (market watcher, research, risk, execution, audit) с обменом через Redis Streams. Состояние для UI кэшируется в `GlobalAppState` и рассылается через `BroadcastManager`.
- **CTO-AI**: конечный автомат, который утверждает или отклоняет торговые гипотезы, контролирует режимы (`manual`/`semi_auto`/`full_auto`) и обеспечивает explainability через события и журналы.
- **Storage**: PostgreSQL для аудита, Redis для шины событий и кэша метаданных, Bybit API (через собственный адаптер) как источник рыночных данных и точка исполнения.
- **Frontend**: React + TypeScript + Vite + Tailwind. Реал-тайм дэшборд с WebSocket-потоком, контролем режимов, аварийным стопом, визуализацией кандидатов и журналом решений.

Подробная схема и решения описаны в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Требования
- Python 3.11+
- PostgreSQL 15+ (можно локально в Docker)
- Redis 7+
- Node.js 20+ и pnpm 8+
- Bybit API ключи (testnet и/или mainnet) — вводятся через переменные окружения сейчас, в будущем UI.

Платформа оптимизирована под недорогой сервер (Intel i3, 7.5 GB RAM): по умолчанию включён `dry_run`, ограничение `max_candidate_symbols`, умеренные интервалы сканирования.

## Быстрый старт (локально)
```bash
# 1. Настройте переменные среды
cp backend/.env.example backend/.env  # отредактируйте ключи и DSN

# 2. Установите зависимости backend
cd backend
poetry install  # или pip install -r requirements.txt после генерации

# 3. Миграции БД (создание таблиц)
poetry run python -m app.scripts.init_db  # создаст таблицу event_logs

# 4. Запустите backend
poetry run uvicorn app.main:app --reload

# 5. Установите фронтенд зависимости
cd ../frontend
pnpm install

# 6. Запустите UI
pnpm dev  # http://localhost:5173
```

### Docker Compose (опционально)
> В разработке. Планируется docker-compose для backend + PostgreSQL + Redis + frontend-build. Пока используйте локальный запуск или собственные контейнеры.

## Конфигурация
Все настройки берутся из Pydantic `Settings` (`backend/app/core/config.py`) и могут быть заданы через `.env`:

| Переменная | Описание | Значение по умолчанию |
|------------|----------|-----------------------|
| `bybit_api_key`, `bybit_api_secret` | Ключи Bybit | `None` (обязательны для реального трейдинга) |
| `bybit_base_url` | API хост | `https://api-testnet.bybit.com` |
| `dry_run` | Тестовый режим | `True` |
| `redis_dsn` | Подключение к Redis | `redis://localhost:6379/0` |
| `database_dsn` | PostgreSQL DSN | `postgresql+asyncpg://user:pass@localhost:5432/cryptoalpha` |
| `market_scan_interval_seconds` | Частота сканера | `10.0` |
| `research_refresh_interval_seconds` | Минимальный интервал для пересчёта гипотезы по символу | `30.0` |
| `research_max_hypotheses_per_minute` | Глобальный лимит генерации гипотез в минуту | `30` |
| `max_candidate_symbols` | Ограничение кандидатов | `10` |
| `max_leverage` | Максимальное плечо | `3.0` |
| `execution_retry_attempts` | Кол-во повторов при ошибке заявки | `3` |
| `execution_retry_backoff_seconds` | Базовая задержка между повторами | `1.0` |
| `execution_degraded_threshold` | Кол-во подряд неудачных заявок до деградации | `3` |
| `execution_degraded_cooldown_seconds` | Длительность деградации исполнения | `120.0` |
| `auto_exposure_enabled` | Включить авто-экспозицию | `False` |
| `auto_exposure_portfolio_pct` | Доля портфеля для авто-экспозиции | `0.1` |
| `auto_symbol_allocation_pct` | Доля на один символ | `0.1` |
| `auto_research_enabled` | Авто-триггеры ResearchEngine | `True` |
| `auto_research_interval_minutes` | Минимальный интервал перезапуска (мин) | `5.0` |
| `auto_research_batch_size` | Сколько символов переиздаётся за цикл | `5` |
| `rl_enabled` | Включить RL-инференс | `False` |
| `rl_policy_min_confidence` | Минимальная уверенность RL | `0.7` |
| `rl_retrain_interval_hours` | Период переобучения RL | `6` |
| `rl_experience_window_days` | Окно опыта RL | `30` |
| `redis_stream_maxlen` | Ограничение длины журналов в Redis Streams | `5000` |

При переключении на mainnet поменяйте:
1. `bybit_base_url` → `https://api.bybit.com`
2. `dry_run` → `False`
3. Убедитесь, что risk-параметры пересмотрены и баланс достаточен.

## Backend сервисы
- **MarketWatcher**: подписывается на рынок, присваивает `market_score`, распределяет по bucket’ам.
- **ResearchEngine**: строит торговые гипотезы, считает `entry/target/stop`, `confidence`, `notional_usdt`, соблюдает per-symbol cooldown и глобальный лимит `research_max_hypotheses_per_minute`.
- **AutoResearchManager**: держит бэклог кандидатов в Redis, периодически отправляет обновлённые `MarketSnapshot` для ResearchEngine, учитывая лимит гипотез и per-symbol cooldown. Параметры управляются через `auto_research_*` в RuntimeConfig, статус виден в дэшборде.
- **RiskEngine**: проверяет лимиты по плечу, экспозиции, дневному убытку, уверенности; может блокировать.
- **CTO-AI**: FSM, принимает решения `OPEN/CLOSE/HOLD/REJECT/NO_TRADE`, управляет режимами.
- **ExecutionEngine**: dry-run или реальные заявки через Bybit REST. Получает только утверждённые CTO-AI решения (через поток `ctoai.decisions`), реализует идемпотентность, повторы, и режим деградации с обратной связью о здоровье сервиса.
- **ExchangePositionWatcher**: периодически запрашивает открытые позиции с Bybit, обновляет глобальное состояние и метрики экспозиции, транслирует их на дэшборд.
- **RLStateBuilder**: собирает признаки из потоков (market/risk/execution), вычисляет метрики портфеля и кеширует в Redis (`rl_state_cache:{symbol}`).
- **RLTrainer**: обучает PPO LSTM actor-critic на накопленном опыте, обновляет `rl_policy:latest` и статистику нормализации.
- **AuditLogger**: пишет события в PostgreSQL (`event_logs`).
- **Notifier**: транслирует состояние в WebSocket клиентов.

## REST & WebSocket API
- `GET /api/health`
- `GET /api/market/overview`
- `GET /api/ctoai/state`
- `GET /api/ctoai/directives`
- `GET /api/ctoai/rejections`
- `POST /api/ctoai/mode {"mode": "manual|semi_auto|full_auto"}`
- `POST /api/ctoai/emergency-stop`
- `GET /api/stats/trades?start&end&symbol&limit&offset`
- `GET /api/stats/trades/summary?start&end`
- `GET /api/stats/trades/export?start&end&symbol`
- `GET /api/exchange/positions`
- `GET /api/rl/status`
- `GET /api/audit/events?limit=100`
- WebSocket: `ws://{host}/ws/dashboard` — рассылает `DashboardState`, включая состояние сервисов (`services.execution-engine.status` и др.).

## Frontend (ctoai-dashboard)
- Стек: React 18, TypeScript, Vite 5, Tailwind, Framer Motion, Recharts.
- Основные блоки: Market overview, CTO-AI status, Mode switch, Active directives, Rejections, Exchange positions, RL status, Audit log, Emergency stop.
- Подключение WebSocket: `createDashboardSocket`, состояние хранит `useDashboard`.
- Построение графика топ-кандидатов: `TopCandidatesChart` (Recharts).
- Раздел «Статистика сделок»: карточки сводных метрик, таблица завершённых сделок, PnL по дням/неделям и кнопка выгрузки CSV. Данные подгружаются из `/api/stats/trades*`.
- Раздел «Открытые позиции (биржа)»: таблица позиций с суммарной экспозицией, чистым плечом и PnL на основе `/api/exchange/positions`.
- Панель «RL статус»: метрики тренировки, политика и список последних закрытых сделок из `/api/rl/status`.

### Режимы работы CTO-AI
- **Full auto** (рекомендуется): CTO-AI самостоятельно утверждает директивы, Execution Engine сразу выставляет лимитные/рыночные заявки с TP/SL по конфигурации.
- **Semi-auto**: CTO-AI формирует директивы и ждёт подтверждения оператора (функционал подтверждения будет доработан отдельно).
- **Manual**: панель «Ручное управление» активируется и позволяет отправлять собственные сигналы в Execution Engine.

Переключение режима выполняется через компонент «Режим CTO-AI» на дэшборде. После смены статуса UI автоматически обновится через WebSocket.

#### Работа в ручном режиме (при необходимости)
1. Переключите режим в `Manual`.
2. В блоке «Ручное управление» заполните тикер, направление, объём и тип ордера. Для `limit` укажите цену.
3. При открытии позиции можно сразу задать TP/SL — значения попадут в заявку на Bybit.
4. Нажмите «Отправить». Заявка отправится в Execution Engine и отобразится среди директив.
5. Для выхода из позиции переключитесь на действие `Закрыть` и отправьте reduce-only ордер.

> Пользовательским сценарием по умолчанию остаётся `Full auto`: ручной режим включайте только для тестов или аварийных ситуаций.

### Статистика сделок и отчётность
- Сервис `TradeStatsRecorder` фиксирует открытие/закрытие с Execution Engine, сохраняя сделки в таблицы `trade_sessions` и `trade_fills`.
- Эндпоинты `/api/stats/trades` и `/summary` выдают постраничный журнал и агрегаты (PnL, win rate, средний R/R, дневные и недельные срезы).
- `/api/stats/trades/export` возвращает CSV для анализа в BI/Excel.
- На фронтенде раздел «Статистика сделок» отображает данные, поддерживает фильтры по датам/символу и экспорт.

### Сборка
```bash
cd frontend
pnpm build
pnpm preview  # статическая раздача собранного UI
```
Сборка помещает артефакты в `frontend/dist`. Их можно обслуживать через любой reverse-proxy (Nginx, Caddy). Для продакшена рекомендуется собрать Docker-образ.

## Мониторинг и журналирование
- Все события (market snapshot, hypotheses, directives, execution, operator commands) пишутся в PostgreSQL через `EventLogRepository`.
- Реал-тайм состояние доступно через UI и WebSocket, включая метрики экспозиции портфеля, открытые позиции и здоровье сервисов. ExecutionEngine сообщает состояние `healthy/unhealthy/degraded`; при деградации директивы автоматически получают статус `degraded` с указанием времени восстановления. В случае проблем используйте `GET /api/audit/events`.
- Структурированные логи backend на `structlog` (stdout).

## Тестирование
- Unit/async тесты (Pytest) — TODO.
- Планируется интеграционный тестовый сценарий: мок Bybit API + dry-run ExecutionEngine + replay market snapshots.
- Для frontend предусмотрена настройка Jest/Vitest (пока не добавлено).

## Безопасность и эксплуатация
- **Ограничение плеча**: `max_leverage = 3`. Проверяется RiskEngine, ExecutionEngine.
- **Dry run**: всегда запускайте на тестнете, пока не убедитесь в корректности.
- **Emergency Stop**: доступен из UI. Блокирует дальнейшие действия CTO-AI.
- **API Keys**: храните в `.env` или секретах оркестратора. Не коммитьте. Планируется ввод через UI с шифрованием.
- **Audit**: храните логи событий 90+ дней. Используйте ротацию PostgreSQL.

## Дальнейшие шаги
- Автоматизация деплоя (Docker Compose / Helm чарты).
- Поддержка Bybit WebSocket для market watcher (снижение задержек).
- Backtesting и симулятор исполнения.
- UI для конфигурации политик CTO-AI и risk параметров.
- Интеграция ML-моделей исследования с explainability (SHAP).

Платформа готова к развёртыванию в тестовой среде и дальнейшему наращиванию функционала. Для вопросов и предложений по улучшению см. `docs/ARCHITECTURE.md` и оставляйте задачи в TODO.
