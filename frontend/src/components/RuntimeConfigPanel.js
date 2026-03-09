import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { FiRotateCcw, FiSave } from 'react-icons/fi';
const NUMBER_FIELDS = [
    {
        key: 'market_scan_interval_seconds',
        label: 'Сканирование рынка (сек)',
        hint: 'Как часто Market Watcher опрашивает Bybit.',
        step: 1,
        min: 1,
        max: 300,
    },
    {
        key: 'research_refresh_interval_seconds',
        label: 'Обновление Research (сек)',
        hint: 'Минимальный интервал между гипотезами по одному символу.',
        step: 5,
        min: 5,
        max: 600,
    },
    {
        key: 'research_max_hypotheses_per_minute',
        label: 'Гипотез в минуту (лимит)',
        hint: 'Глобальный лимит публикаций ResearchEngine в минуту.',
        step: 5,
        min: 1,
        max: 600,
    },
    {
        key: 'funding_threshold',
        label: 'Порог funding',
        hint: 'Минимальный funding rate для добавления заметки.',
        step: 0.001,
        min: 0,
        max: 0.1,
    },
    {
        key: 'volatility_threshold',
        label: 'Порог волатильности',
        hint: 'Используется для классификации сетапов.',
        step: 0.001,
        min: 0,
        max: 0.1,
    },
    {
        key: 'max_candidate_symbols',
        label: 'Кандидатов максимум',
        hint: 'Сколько инструментов попадает в столбец Candidate.',
        step: 1,
        min: 1,
        max: 50,
    },
    {
        key: 'position_manager_limit_exit_timeout_seconds',
        label: 'Limit-exit таймаут (сек)',
        hint: 'Если стоп/тейк закрывается лимиткой и не исполнился за это время, будет fallback в market.',
        step: 1,
        min: 0,
        max: 600,
    },
    {
        key: 'max_portfolio_exposure_usdt',
        label: 'Макс. экспозиция (USDT)',
        hint: 'Глобальный лимит по всем позициям.',
        step: 100,
        min: 100,
        max: 1_000_000,
    },
    {
        key: 'max_symbol_allocation_pct',
        label: 'Лимит на символ (%)',
        hint: 'Доля лимита для одной пары.',
        step: 0.01,
        min: 0.01,
        max: 1,
    },
    {
        key: 'auto_exposure_portfolio_pct',
        label: 'Auto: доля портфеля',
        hint: 'Какая часть свободной маржи доступна для сделок при автонастройке.',
        step: 0.01,
        min: 0,
        max: 1,
    },
    {
        key: 'auto_symbol_allocation_pct',
        label: 'Auto: доля на символ',
        hint: 'Лимит для одного инструмента в режиме автоэкспозиции.',
        step: 0.01,
        min: 0,
        max: 1,
    },
    {
        key: 'auto_research_interval_minutes',
        label: 'Auto-research: интервал (мин)',
        hint: 'Минимальная задержка между циклами авто-исследования.',
        step: 1,
        min: 1,
        max: 240,
    },
    {
        key: 'auto_research_batch_size',
        label: 'Auto-research: размер батча',
        hint: 'Сколько символов отправляется за одну волну.',
        step: 1,
        min: 1,
        max: 50,
    },
    {
        key: 'max_leverage',
        label: 'Макс. плечо',
        hint: 'CTO-AI не будет превышать этот уровень.',
        step: 0.5,
        min: 1,
        max: 50,
    },
    {
        key: 'min_confidence_threshold',
        label: 'Мин. уверенность CTO-AI',
        hint: 'Гипотезы ниже порога будут отсеяны.',
        step: 0.01,
        min: 0,
        max: 1,
    },
    {
        key: 'default_stop_loss_pct',
        label: 'Стоп-лосс (%)',
        hint: 'Базовый риск на сделку, используется для автозакрытия.',
        step: 0.01,
        min: 0,
        max: 1,
    },
    {
        key: 'default_take_profit_pct',
        label: 'Тейк-профит (%)',
        hint: 'Цель по прибыли относительно цены входа.',
        step: 0.01,
        min: 0,
        max: 2,
    },
    {
        key: 'execution_retry_attempts',
        label: 'Execution: повторы',
        hint: 'Количество повторов ордера при ошибке.',
        step: 1,
        min: 0,
        max: 10,
    },
    {
        key: 'execution_retry_backoff_seconds',
        label: 'Execution: backoff (сек)',
        hint: 'Начальная задержка между повторами.',
        step: 0.5,
        min: 0,
        max: 30,
    },
    {
        key: 'execution_degraded_threshold',
        label: 'Execution: порог деградации',
        hint: 'Сколько подряд ошибок до перехода в degraded.',
        step: 1,
        min: 1,
        max: 20,
    },
    {
        key: 'execution_degraded_cooldown_seconds',
        label: 'Execution: cooldown (сек)',
        hint: 'Длительность окна деградации.',
        step: 10,
        min: 10,
        max: 3600,
    },
    {
        key: 'max_trades_per_day',
        label: 'Лимит сделок в день',
        hint: 'Если превышен — RiskEngine будет блокировать новые открытия позиций.',
        step: 1,
        min: 0,
        max: 10000,
    },
    {
        key: 'max_daily_loss_usdt',
        label: 'Лимит дневного убытка (USDT)',
        hint: 'Если PnL за сегодня ниже -лимита — новые открытия будут блокированы.',
        step: 1,
        min: 0,
        max: 1000000,
    },
    {
        key: 'max_consecutive_losses',
        label: 'Лимит подряд убыточных',
        hint: 'Если подряд слишком много лоссов — новые открытия будут блокированы.',
        step: 1,
        min: 0,
        max: 10000,
    },
    {
        key: 'rl_policy_min_confidence',
        label: 'RL: мин. уверенность политики',
        hint: 'Порог доверия для применения рекомендаций RL.',
        step: 0.01,
        min: 0,
        max: 1,
    },
    {
        key: 'rl_retrain_interval_hours',
        label: 'RL: переобучение (часы)',
        hint: 'Интервал запуска PPO-тренировки.',
        step: 1,
        min: 1,
        max: 24,
    },
    {
        key: 'rl_experience_window_days',
        label: 'RL: окно опыта (дни)',
        hint: 'Сколько дней сделок включается в буфер обучения.',
        step: 1,
        min: 1,
        max: 180,
    },
];
export function RuntimeConfigPanel({ config, saving, onSubmit }) {
    const [draft, setDraft] = useState(config);
    useEffect(() => {
        if (config) {
            setDraft(config);
        }
    }, [config]);
    const isDirty = useMemo(() => {
        if (!config || !draft) {
            return false;
        }
        const numbersChanged = NUMBER_FIELDS.some(({ key }) => draft[key] !== config[key]);
        const dryRunChanged = draft.dry_run !== config.dry_run;
        const rlEnabledChanged = draft.rl_enabled !== config.rl_enabled;
        const autoExposureChanged = draft.auto_exposure_enabled !== config.auto_exposure_enabled;
        const autoResearchChanged = draft.auto_research_enabled !== config.auto_research_enabled;
        const marketExitChanged = draft.position_manager_use_market_exit !== config.position_manager_use_market_exit;
        const denylistChanged = (draft.symbol_denylist || []).join(',') !== (config.symbol_denylist || []).join(',');
        return numbersChanged || dryRunChanged || rlEnabledChanged || autoExposureChanged || autoResearchChanged || marketExitChanged || denylistChanged;
    }, [config, draft]);
    if (!draft || !config) {
        return (_jsxs("section", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card", children: [_jsx("h2", { className: "text-lg font-semibold text-white", children: "\u041F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u044B CTO-AI" }), _jsx("p", { className: "mt-4 text-sm text-slate-400", children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0442\u0435\u043A\u0443\u0449\u0438\u0445 \u043D\u0430\u0441\u0442\u0440\u043E\u0435\u043A\u2026" })] }));
    }
    const updatedAt = config.updated_at ? new Date(config.updated_at).toLocaleString() : null;
    const handleNumberChange = (key, value) => {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return;
        }
        setDraft((prev) => (prev ? { ...prev, [key]: numeric } : prev));
    };
    const toggleDryRun = () => {
        setDraft((prev) => (prev ? { ...prev, dry_run: !prev.dry_run } : prev));
    };
    const toggleRlEnabled = () => {
        setDraft((prev) => (prev ? { ...prev, rl_enabled: !prev.rl_enabled } : prev));
    };
    const toggleAutoExposure = () => {
        setDraft((prev) => (prev ? { ...prev, auto_exposure_enabled: !prev.auto_exposure_enabled } : prev));
    };
    const toggleAutoResearch = () => {
        setDraft((prev) => (prev ? { ...prev, auto_research_enabled: !prev.auto_research_enabled } : prev));
    };
    const toggleMarketExit = () => {
        setDraft((prev) => (prev ? { ...prev, position_manager_use_market_exit: !prev.position_manager_use_market_exit } : prev));
    };
    const handleDenylistChange = (value) => {
        const parsed = value
            .split(/\r?\n|,/)
            .map((item) => item.trim())
            .filter((item) => item.length > 0);
        setDraft((prev) => (prev ? { ...prev, symbol_denylist: parsed } : prev));
    };
    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!config || !draft) {
            return;
        }
        const payload = {};
        const numericPayload = payload;
        for (const { key } of NUMBER_FIELDS) {
            const nextValue = draft[key];
            const currentValue = config[key];
            if (typeof nextValue === 'number' && nextValue !== currentValue) {
                numericPayload[key] = nextValue;
            }
        }
        if (draft.auto_exposure_enabled !== config.auto_exposure_enabled) {
            payload.auto_exposure_enabled = draft.auto_exposure_enabled;
        }
        if (draft.auto_research_enabled !== config.auto_research_enabled) {
            payload.auto_research_enabled = draft.auto_research_enabled;
        }
        if (draft.position_manager_use_market_exit !== config.position_manager_use_market_exit) {
            payload.position_manager_use_market_exit = draft.position_manager_use_market_exit;
        }
        if ((draft.symbol_denylist || []).join(',') !== (config.symbol_denylist || []).join(',')) {
            payload.symbol_denylist = draft.symbol_denylist;
        }
        if (draft.dry_run !== config.dry_run) {
            payload.dry_run = draft.dry_run;
        }
        if (draft.rl_enabled !== config.rl_enabled) {
            payload.rl_enabled = draft.rl_enabled;
        }
        await onSubmit(payload);
    };
    const resetDraft = () => {
        setDraft(config);
    };
    return (_jsxs("section", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card", children: [_jsxs("div", { className: "flex flex-col gap-2 md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { children: [_jsx("h2", { className: "text-lg font-semibold text-white", children: "\u041F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u044B CTO-AI" }), _jsx("p", { className: "text-sm text-slate-400", children: "\u0420\u0435\u0434\u0430\u043A\u0442\u0438\u0440\u0443\u0439\u0442\u0435 \u043B\u0438\u043C\u0438\u0442\u044B \u0438 \u0438\u043D\u0442\u0435\u0440\u0432\u0430\u043B\u044B \u043F\u0440\u044F\u043C\u043E \u0441 \u043F\u0430\u043D\u0435\u043B\u0438." })] }), updatedAt && _jsxs("span", { className: "text-xs text-slate-500", children: ["\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u043E: ", updatedAt] })] }), _jsxs("form", { className: "mt-6 space-y-6", onSubmit: handleSubmit, children: [_jsx("div", { className: "grid gap-4 md:grid-cols-2", children: NUMBER_FIELDS.map(({ key, label, hint, step, min, max }) => (_jsxs("label", { className: "flex flex-col gap-2 rounded-xl border border-slate-800 bg-slate-950/40 p-4", children: [_jsx("span", { className: "text-sm font-medium text-slate-200", children: label }), _jsx("input", { type: "number", step: step, min: min, max: max, value: draft[key]?.toString() ?? '', onChange: (event) => handleNumberChange(key, event.target.value), className: "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" }), _jsx("span", { className: "text-xs text-slate-500", children: hint })] }, key))) }), _jsxs("div", { className: "grid gap-3 md:grid-cols-2", children: [_jsxs("div", { className: "flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm font-medium text-slate-200", children: "Auto-\u044D\u043A\u0441\u043F\u043E\u0437\u0438\u0446\u0438\u044F" }), _jsx("p", { className: "text-xs text-slate-500", children: "\u041F\u0440\u0438 \u0432\u043A\u043B\u044E\u0447\u0435\u043D\u0438\u0438 \u043B\u0438\u043C\u0438\u0442\u044B \u0432\u044B\u0441\u0447\u0438\u0442\u044B\u0432\u0430\u044E\u0442\u0441\u044F \u043E\u0442 \u0434\u043E\u0441\u0442\u0443\u043F\u043D\u043E\u0439 \u043C\u0430\u0440\u0436\u0438 \u043D\u0430 Bybit \u043A\u0430\u0436\u0434\u044B\u0435 ~30 \u0441\u0435\u043A\u0443\u043D\u0434." })] }), _jsxs("button", { type: "button", onClick: toggleAutoExposure, className: `inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.auto_exposure_enabled
                                            ? 'border-emerald-400/60 bg-emerald-500/10 text-emerald-200'
                                            : 'border-slate-700 bg-slate-900/70 text-slate-300'}`, children: [_jsx("span", { className: `h-2 w-2 rounded-full ${draft.auto_exposure_enabled ? 'bg-emerald-300' : 'bg-slate-500'}` }), draft.auto_exposure_enabled ? 'Автонастройка включена' : 'Автонастройка выключена'] })] }), _jsxs("div", { className: "flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm font-medium text-slate-200", children: "Auto-Research" }), _jsx("p", { className: "text-xs text-slate-500", children: "\u041F\u0435\u0440\u0435\u0438\u0437\u0434\u0430\u0451\u0442 \u043A\u0430\u043D\u0434\u0438\u0434\u0430\u0442\u043E\u0432 \u0432 ResearchEngine \u043F\u043E \u0440\u0430\u0441\u043F\u0438\u0441\u0430\u043D\u0438\u044E, \u0438\u0441\u043F\u043E\u043B\u044C\u0437\u0443\u044F \u043F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u044B \u043D\u0438\u0436\u0435." })] }), _jsxs("button", { type: "button", onClick: toggleAutoResearch, "aria-label": "\u041F\u0435\u0440\u0435\u043A\u043B\u044E\u0447\u0438\u0442\u044C auto-research", "aria-pressed": draft.auto_research_enabled, "data-testid": "auto-research-toggle", className: `inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.auto_research_enabled
                                            ? 'border-sky-400/60 bg-sky-500/10 text-sky-200'
                                            : 'border-slate-700 bg-slate-900/70 text-slate-300'}`, children: [_jsx("span", { className: `h-2 w-2 rounded-full ${draft.auto_research_enabled ? 'bg-sky-300' : 'bg-slate-500'}` }), draft.auto_research_enabled ? 'Auto-Research включён' : 'Auto-Research выключен'] })] }), _jsxs("div", { className: "flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm font-medium text-slate-200", children: "\u0420\u0435\u0436\u0438\u043C Dry-run" }), _jsx("p", { className: "text-xs text-slate-500", children: "\u041F\u0440\u0438 \u0432\u043A\u043B\u044E\u0447\u0435\u043D\u0438\u0438 \u0437\u0430\u044F\u0432\u043A\u0438 \u043D\u0435 \u043E\u0442\u043F\u0440\u0430\u0432\u043B\u044F\u044E\u0442\u0441\u044F \u043D\u0430 \u0431\u0438\u0440\u0436\u0443." })] }), _jsxs("button", { type: "button", onClick: toggleDryRun, className: `inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.dry_run
                                            ? 'border-amber-400/50 bg-amber-400/10 text-amber-200'
                                            : 'border-emerald-400/50 bg-emerald-400/10 text-emerald-200'}`, children: [_jsx("span", { className: "h-2 w-2 rounded-full bg-current" }), draft.dry_run ? 'Dry-run включён' : 'Работаем на реальном рынке'] })] }), _jsxs("div", { className: "flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm font-medium text-slate-200", children: "\u0412\u044B\u0445\u043E\u0434 \u043F\u043E \u0441\u0442\u043E\u043F\u0443" }), _jsx("p", { className: "text-xs text-slate-500", children: "\u0411\u0435\u0437\u043E\u043F\u0430\u0441\u043D\u044B\u0439 \u0440\u0435\u0436\u0438\u043C: limit-\u0432\u044B\u0445\u043E\u0434 \u0443\u043C\u0435\u043D\u044C\u0448\u0430\u0435\u0442 \u043F\u0440\u043E\u0441\u043A\u0430\u043B\u044C\u0437\u044B\u0432\u0430\u043D\u0438\u0435, \u043D\u043E \u043C\u043E\u0436\u0435\u0442 \u043D\u0435 \u0437\u0430\u043A\u0440\u044B\u0442\u044C \u043F\u043E\u0437\u0438\u0446\u0438\u044E \u043C\u0433\u043D\u043E\u0432\u0435\u043D\u043D\u043E." })] }), _jsxs("button", { type: "button", onClick: toggleMarketExit, className: `inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.position_manager_use_market_exit
                                            ? 'border-rose-400/50 bg-rose-400/10 text-rose-200'
                                            : 'border-emerald-400/50 bg-emerald-400/10 text-emerald-200'}`, children: [_jsx("span", { className: "h-2 w-2 rounded-full bg-current" }), draft.position_manager_use_market_exit ? 'Market exit (агрессивно)' : 'Limit exit (безопасно)'] })] }), _jsxs("div", { className: "flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4 md:col-span-2", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm font-medium text-slate-200", children: "Ban-\u043B\u0438\u0441\u0442 \u0441\u0438\u043C\u0432\u043E\u043B\u043E\u0432" }), _jsx("p", { className: "text-xs text-slate-500", children: "\u0421\u0438\u043C\u0432\u043E\u043B\u044B \u0438\u0437 \u0441\u043F\u0438\u0441\u043A\u0430 \u043D\u0435 \u0431\u0443\u0434\u0443\u0442 \u043E\u0442\u043A\u0440\u044B\u0432\u0430\u0442\u044C\u0441\u044F (OPEN). \u0417\u0430\u043A\u0440\u044B\u0442\u0438\u044F (CLOSE) \u043D\u0435 \u0431\u043B\u043E\u043A\u0438\u0440\u0443\u044E\u0442\u0441\u044F. \u041E\u0434\u0438\u043D \u0441\u0438\u043C\u0432\u043E\u043B \u0432 \u0441\u0442\u0440\u043E\u043A\u0435 \u0438\u043B\u0438 \u0447\u0435\u0440\u0435\u0437 \u0437\u0430\u043F\u044F\u0442\u0443\u044E." })] }), _jsx("textarea", { value: (draft.symbol_denylist || []).join('\n'), onChange: (event) => handleDenylistChange(event.target.value), rows: 4, className: "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("div", { className: "flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm font-medium text-slate-200", children: "\u0412\u043A\u043B\u044E\u0447\u0438\u0442\u044C RL-\u043F\u043E\u043B\u0438\u0442\u0438\u043A\u0443" }), _jsx("p", { className: "text-xs text-slate-500", children: "\u041F\u0440\u0438 \u0430\u043A\u0442\u0438\u0432\u0430\u0446\u0438\u0438 CTO-AI \u043F\u043E\u0434\u0442\u044F\u0433\u0438\u0432\u0430\u0435\u0442 \u0441\u043E\u0432\u0435\u0442\u044B PPO-\u043F\u043E\u043B\u0438\u0442\u0438\u043A\u0438 \u043F\u0435\u0440\u0435\u0434 \u0444\u0438\u043D\u0430\u043B\u044C\u043D\u044B\u043C \u0440\u0435\u0448\u0435\u043D\u0438\u0435\u043C." })] }), _jsxs("button", { type: "button", onClick: toggleRlEnabled, className: `inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.rl_enabled
                                            ? 'border-indigo-400/60 bg-indigo-500/15 text-indigo-200'
                                            : 'border-slate-700 bg-slate-900/70 text-slate-300'}`, children: [_jsx("span", { className: `h-2 w-2 rounded-full ${draft.rl_enabled ? 'bg-indigo-300' : 'bg-slate-500'}` }), draft.rl_enabled ? 'RL активен' : 'RL выключен'] })] })] }), _jsxs("div", { className: "flex flex-wrap items-center gap-3", children: [_jsxs("button", { type: "submit", disabled: saving || !isDirty, className: `inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium transition ${saving || !isDirty
                                    ? 'cursor-not-allowed border border-slate-700 bg-slate-800/60 text-slate-400'
                                    : 'border border-indigo-400/60 bg-indigo-500/10 text-indigo-200 hover:bg-indigo-500/20'}`, children: [_jsx(FiSave, { className: "text-base" }), "\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C"] }), _jsxs("button", { type: "button", onClick: resetDraft, disabled: saving || !isDirty, className: "inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:border-slate-600 hover:bg-slate-800/80 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500", children: [_jsx(FiRotateCcw, {}), "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C"] })] })] })] }));
}
