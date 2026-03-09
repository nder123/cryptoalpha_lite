import { useEffect, useMemo, useState } from 'react';
import { FiRotateCcw, FiSave } from 'react-icons/fi';

import type { RuntimeConfig, RuntimeConfigUpdatePayload } from '../types';

type NumericRuntimeConfigKey = Exclude<
    keyof RuntimeConfigUpdatePayload,
    'auto_exposure_enabled' | 'dry_run' | 'rl_enabled' | 'auto_research_enabled' | 'position_manager_use_market_exit' | 'symbol_denylist'
>;

const NUMBER_FIELDS: Array<{
    key: NumericRuntimeConfigKey;
    label: string;
    hint: string;
    step: number;
    min?: number;
    max?: number;
}> = [
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

type Props = {
    config: RuntimeConfig | null;
    saving: boolean;
    onSubmit: (payload: RuntimeConfigUpdatePayload) => Promise<void>;
};

export function RuntimeConfigPanel({ config, saving, onSubmit }: Props) {
    const [draft, setDraft] = useState<RuntimeConfig | null>(config);

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
        return (
            <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card">
                <h2 className="text-lg font-semibold text-white">Параметры CTO-AI</h2>
                <p className="mt-4 text-sm text-slate-400">Загрузка текущих настроек…</p>
            </section>
        );
    }

    const updatedAt = config.updated_at ? new Date(config.updated_at).toLocaleString() : null;

    const handleNumberChange = (key: NumericRuntimeConfigKey, value: string) => {
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

    const handleDenylistChange = (value: string) => {
        const parsed = value
            .split(/\r?\n|,/)
            .map((item) => item.trim())
            .filter((item) => item.length > 0);
        setDraft((prev) => (prev ? { ...prev, symbol_denylist: parsed } : prev));
    };

    const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!config || !draft) {
            return;
        }
        const payload: RuntimeConfigUpdatePayload = {};
        const numericPayload = payload as unknown as Partial<Record<NumericRuntimeConfigKey, number>>;
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

    return (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-white">Параметры CTO-AI</h2>
                    <p className="text-sm text-slate-400">Редактируйте лимиты и интервалы прямо с панели.</p>
                </div>
                {updatedAt && <span className="text-xs text-slate-500">Обновлено: {updatedAt}</span>}
            </div>

            <form className="mt-6 space-y-6" onSubmit={handleSubmit}>
                <div className="grid gap-4 md:grid-cols-2">
                    {NUMBER_FIELDS.map(({ key, label, hint, step, min, max }) => (
                        <label key={key} className="flex flex-col gap-2 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                            <span className="text-sm font-medium text-slate-200">{label}</span>
                            <input
                                type="number"
                                step={step}
                                min={min}
                                max={max}
                                value={draft[key]?.toString() ?? ''}
                                onChange={(event) => handleNumberChange(key, event.target.value)}
                                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                            <span className="text-xs text-slate-500">{hint}</span>
                        </label>
                    ))}
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                    <div className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                        <div>
                            <p className="text-sm font-medium text-slate-200">Auto-экспозиция</p>
                            <p className="text-xs text-slate-500">
                                При включении лимиты высчитываются от доступной маржи на Bybit каждые ~30 секунд.
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={toggleAutoExposure}
                            className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.auto_exposure_enabled
                                ? 'border-emerald-400/60 bg-emerald-500/10 text-emerald-200'
                                : 'border-slate-700 bg-slate-900/70 text-slate-300'
                                }`}
                        >
                            <span className={`h-2 w-2 rounded-full ${draft.auto_exposure_enabled ? 'bg-emerald-300' : 'bg-slate-500'}`} />
                            {draft.auto_exposure_enabled ? 'Автонастройка включена' : 'Автонастройка выключена'}
                        </button>
                    </div>
                    <div className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                        <div>
                            <p className="text-sm font-medium text-slate-200">Auto-Research</p>
                            <p className="text-xs text-slate-500">
                                Переиздаёт кандидатов в ResearchEngine по расписанию, используя параметры ниже.
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={toggleAutoResearch}
                            aria-label="Переключить auto-research"
                            aria-pressed={draft.auto_research_enabled}
                            data-testid="auto-research-toggle"
                            className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.auto_research_enabled
                                ? 'border-sky-400/60 bg-sky-500/10 text-sky-200'
                                : 'border-slate-700 bg-slate-900/70 text-slate-300'
                                }`}
                        >
                            <span className={`h-2 w-2 rounded-full ${draft.auto_research_enabled ? 'bg-sky-300' : 'bg-slate-500'}`} />
                            {draft.auto_research_enabled ? 'Auto-Research включён' : 'Auto-Research выключен'}
                        </button>
                    </div>
                    <div className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                        <div>
                            <p className="text-sm font-medium text-slate-200">Режим Dry-run</p>
                            <p className="text-xs text-slate-500">При включении заявки не отправляются на биржу.</p>
                        </div>
                        <button
                            type="button"
                            onClick={toggleDryRun}
                            className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.dry_run
                                ? 'border-amber-400/50 bg-amber-400/10 text-amber-200'
                                : 'border-emerald-400/50 bg-emerald-400/10 text-emerald-200'
                                }`}
                        >
                            <span className="h-2 w-2 rounded-full bg-current" />
                            {draft.dry_run ? 'Dry-run включён' : 'Работаем на реальном рынке'}
                        </button>
                    </div>

                    <div className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                        <div>
                            <p className="text-sm font-medium text-slate-200">Выход по стопу</p>
                            <p className="text-xs text-slate-500">Безопасный режим: limit-выход уменьшает проскальзывание, но может не закрыть позицию мгновенно.</p>
                        </div>
                        <button
                            type="button"
                            onClick={toggleMarketExit}
                            className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.position_manager_use_market_exit
                                ? 'border-rose-400/50 bg-rose-400/10 text-rose-200'
                                : 'border-emerald-400/50 bg-emerald-400/10 text-emerald-200'
                                }`}
                        >
                            <span className="h-2 w-2 rounded-full bg-current" />
                            {draft.position_manager_use_market_exit ? 'Market exit (агрессивно)' : 'Limit exit (безопасно)'}
                        </button>
                    </div>

                    <div className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4 md:col-span-2">
                        <div>
                            <p className="text-sm font-medium text-slate-200">Ban-лист символов</p>
                            <p className="text-xs text-slate-500">Символы из списка не будут открываться (OPEN). Закрытия (CLOSE) не блокируются. Один символ в строке или через запятую.</p>
                        </div>
                        <textarea
                            value={(draft.symbol_denylist || []).join('\n')}
                            onChange={(event) => handleDenylistChange(event.target.value)}
                            rows={4}
                            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        />
                    </div>
                    <div className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                        <div>
                            <p className="text-sm font-medium text-slate-200">Включить RL-политику</p>
                            <p className="text-xs text-slate-500">
                                При активации CTO-AI подтягивает советы PPO-политики перед финальным решением.
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={toggleRlEnabled}
                            className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${draft.rl_enabled
                                ? 'border-indigo-400/60 bg-indigo-500/15 text-indigo-200'
                                : 'border-slate-700 bg-slate-900/70 text-slate-300'
                                }`}
                        >
                            <span className={`h-2 w-2 rounded-full ${draft.rl_enabled ? 'bg-indigo-300' : 'bg-slate-500'}`} />
                            {draft.rl_enabled ? 'RL активен' : 'RL выключен'}
                        </button>
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                    <button
                        type="submit"
                        disabled={saving || !isDirty}
                        className={`inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium transition ${saving || !isDirty
                            ? 'cursor-not-allowed border border-slate-700 bg-slate-800/60 text-slate-400'
                            : 'border border-indigo-400/60 bg-indigo-500/10 text-indigo-200 hover:bg-indigo-500/20'
                            }`}
                    >
                        <FiSave className="text-base" />
                        Сохранить
                    </button>
                    <button
                        type="button"
                        onClick={resetDraft}
                        disabled={saving || !isDirty}
                        className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:border-slate-600 hover:bg-slate-800/80 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
                    >
                        <FiRotateCcw />
                        Сбросить
                    </button>
                </div>
            </form>
        </section>
    );
}
