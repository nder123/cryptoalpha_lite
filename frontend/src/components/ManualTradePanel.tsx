import { useCallback, useMemo, useState } from 'react';
import { FiSend } from 'react-icons/fi';

import { submitManualDirective } from '../api';
import type { ManualDirectivePayload } from '../types';

type Props = {
    onNotify: (message: string) => void;
    disabled?: boolean;
    modeLabel?: string;
};

type FormState = {
    symbol: string;
    direction: 'long' | 'short';
    action: 'open' | 'close';
    order_type: 'market' | 'limit';
    quantity: string;
    price: string;
    take_profit_price: string;
    stop_loss_price: string;
    time_in_force: 'GTC' | 'IOC' | 'FOK';
    leverage: string;
    confidence: string;
    expires_in_minutes: string;
    reduce_only: boolean;
};

const DEFAULT_FORM: FormState = {
    symbol: 'BTCUSDT',
    direction: 'long',
    action: 'open',
    order_type: 'market',
    quantity: '0.1',
    price: '',
    take_profit_price: '',
    stop_loss_price: '',
    time_in_force: 'GTC',
    leverage: '1',
    confidence: '0.8',
    expires_in_minutes: '5',
    reduce_only: false,
};

const TIME_IN_FORCE_OPTIONS: Array<{ value: FormState['time_in_force']; label: string }> = [
    { value: 'GTC', label: 'GTC' },
    { value: 'IOC', label: 'IOC' },
    { value: 'FOK', label: 'FOK' },
];

export function ManualTradePanel({ onNotify, disabled = false, modeLabel }: Props) {
    const [form, setForm] = useState<FormState>(DEFAULT_FORM);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const isLimitOrder = form.order_type === 'limit';
    const isOpenAction = form.action === 'open';
    const isFormLocked = disabled || submitting;

    const updateForm = useCallback((patch: Partial<FormState>) => {
        setForm((prev) => ({ ...prev, ...patch }));
    }, []);

    const resetForm = useCallback(() => {
        setForm({ ...DEFAULT_FORM });
        setError(null);
    }, []);

    const parsedQuantity = useMemo(() => Number(form.quantity), [form.quantity]);
    const parsedPrice = useMemo(() => Number(form.price), [form.price]);
    const parsedTP = useMemo(() => Number(form.take_profit_price), [form.take_profit_price]);
    const parsedSL = useMemo(() => Number(form.stop_loss_price), [form.stop_loss_price]);

    const handleSubmit = useCallback(
        async (event: React.FormEvent<HTMLFormElement>) => {
            event.preventDefault();
            if (disabled) {
                return;
            }
            setError(null);

            if (!form.symbol.trim()) {
                setError('Укажите тикер инструмента.');
                return;
            }

            if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
                setError('Объём должен быть положительным числом.');
                return;
            }

            if (isLimitOrder && (!Number.isFinite(parsedPrice) || parsedPrice <= 0)) {
                setError('Для лимитного ордера требуется положительная цена.');
                return;
            }

            if (isOpenAction) {
                if (form.take_profit_price && (!Number.isFinite(parsedTP) || parsedTP <= 0)) {
                    setError('Тейк-профит должен быть положительным числом.');
                    return;
                }
                if (form.stop_loss_price && (!Number.isFinite(parsedSL) || parsedSL <= 0)) {
                    setError('Стоп-лосс должен быть положительным числом.');
                    return;
                }
            }

            const payload: ManualDirectivePayload = {
                symbol: form.symbol.trim().toUpperCase(),
                direction: form.direction,
                action: form.action,
                order_type: form.order_type,
                quantity: parsedQuantity,
                time_in_force: form.time_in_force,
            };

            if (isLimitOrder && Number.isFinite(parsedPrice)) {
                payload.price = parsedPrice;
            }

            if (isOpenAction) {
                if (form.take_profit_price && Number.isFinite(parsedTP)) {
                    payload.take_profit_price = parsedTP;
                }
                if (form.stop_loss_price && Number.isFinite(parsedSL)) {
                    payload.stop_loss_price = parsedSL;
                }
                if (form.reduce_only) {
                    payload.reduce_only = true;
                }
            } else {
                payload.reduce_only = true;
            }

            const leverage = Number(form.leverage);
            if (Number.isFinite(leverage) && leverage > 0) {
                payload.leverage = leverage;
            }

            const confidence = Number(form.confidence);
            if (Number.isFinite(confidence) && confidence >= 0 && confidence <= 1) {
                payload.confidence = confidence;
            }

            const expires = Number(form.expires_in_minutes);
            if (Number.isFinite(expires) && expires > 0) {
                payload.expires_in_minutes = Math.round(expires);
            }

            setSubmitting(true);
            try {
                const directive = await submitManualDirective(payload);
                onNotify(`Заявка отправлена: ${directive.symbol} (${directive.action})`);
                resetForm();
            } catch (err) {
                const message = err instanceof Error ? err.message : 'Не удалось отправить команду';
                setError(message);
                onNotify(message);
            } finally {
                setSubmitting(false);
            }
        },
        [form, isLimitOrder, isOpenAction, onNotify, parsedQuantity, parsedPrice, parsedTP, parsedSL, resetForm]
    );

    const handleActionChange = useCallback(
        (nextAction: FormState['action']) => {
            updateForm({
                action: nextAction,
                reduce_only: nextAction === 'close' ? true : form.reduce_only,
                take_profit_price: nextAction === 'open' ? form.take_profit_price : '',
                stop_loss_price: nextAction === 'open' ? form.stop_loss_price : '',
            });
        },
        [form.reduce_only, form.stop_loss_price, form.take_profit_price, updateForm]
    );

    return (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-white">Ручное управление</h2>
                    <p className="text-sm text-slate-400">Формируйте сигналы вручную — они сразу попадают в Execution Engine.</p>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-500">
                    {disabled && <span>Доступно только в ручном режиме{modeLabel ? ` (${modeLabel})` : ''}</span>}
                    {submitting && <span>Отправка заявки…</span>}
                </div>
            </div>

            <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
                <fieldset disabled={isFormLocked} className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Тикер
                        <input
                            type="text"
                            value={form.symbol}
                            onChange={(event) => updateForm({ symbol: event.target.value.toUpperCase() })}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            placeholder="например, BTCUSDT"
                        />
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Объём
                        <input
                            type="number"
                            step="0.001"
                            min="0"
                            value={form.quantity}
                            onChange={(event) => updateForm({ quantity: event.target.value })}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        />
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Направление
                        <select
                            value={form.direction}
                            onChange={(event) => updateForm({ direction: event.target.value as FormState['direction'] })}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        >
                            <option value="long">Лонг</option>
                            <option value="short">Шорт</option>
                        </select>
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Действие
                        <select
                            value={form.action}
                            onChange={(event) => handleActionChange(event.target.value as FormState['action'])}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        >
                            <option value="open">Открыть позицию</option>
                            <option value="close">Закрыть позицию</option>
                        </select>
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Тип ордера
                        <select
                            value={form.order_type}
                            onChange={(event) =>
                                updateForm({
                                    order_type: event.target.value as FormState['order_type'],
                                    price: event.target.value === 'limit' ? form.price : '',
                                })
                            }
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        >
                            <option value="market">Market</option>
                            <option value="limit">Limit</option>
                        </select>
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Цена (для Limit)
                        <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={form.price}
                            onChange={(event) => updateForm({ price: event.target.value })}
                            disabled={!isLimitOrder}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/70"
                        />
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Плечо
                        <input
                            type="number"
                            step="0.1"
                            min="0"
                            value={form.leverage}
                            onChange={(event) => updateForm({ leverage: event.target.value })}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        />
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Time-in-force
                        <select
                            value={form.time_in_force}
                            onChange={(event) => updateForm({ time_in_force: event.target.value as FormState['time_in_force'] })}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        >
                            {TIME_IN_FORCE_OPTIONS.map((option) => (
                                <option value={option.value} key={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Уверенность (0-1)
                        <input
                            type="number"
                            step="0.01"
                            min="0"
                            max="1"
                            value={form.confidence}
                            onChange={(event) => updateForm({ confidence: event.target.value })}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        />
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-slate-300">
                        Срок действия (мин)
                        <input
                            type="number"
                            min="0"
                            step="1"
                            value={form.expires_in_minutes}
                            onChange={(event) => updateForm({ expires_in_minutes: event.target.value })}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        />
                    </label>
                    <label className="flex items-center gap-3 text-sm text-slate-300">
                        <input
                            type="checkbox"
                            checked={form.reduce_only || !isOpenAction}
                            disabled={!isOpenAction || isFormLocked}
                            onChange={(event) => updateForm({ reduce_only: event.target.checked })}
                            className="h-4 w-4 rounded border border-slate-600 bg-slate-900 text-indigo-500 focus:ring-2 focus:ring-indigo-500"
                        />
                        Reduce only
                    </label>
                </fieldset>

                {isOpenAction && (
                    <fieldset disabled={isFormLocked} className="grid gap-4 md:grid-cols-2">
                        <label className="flex flex-col gap-2 text-sm text-slate-300">
                            Тейк-профит
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                value={form.take_profit_price}
                                onChange={(event) => updateForm({ take_profit_price: event.target.value })}
                                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <label className="flex flex-col gap-2 text-sm text-slate-300">
                            Стоп-лосс
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                value={form.stop_loss_price}
                                onChange={(event) => updateForm({ stop_loss_price: event.target.value })}
                                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                    </fieldset>
                )}

                {error && <p className="text-sm text-rose-400">{error}</p>}

                <div className="flex flex-wrap items-center gap-3">
                    <button
                        type="submit"
                        disabled={isFormLocked}
                        className="inline-flex items-center gap-2 rounded-full bg-indigo-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        <FiSend className="text-base" />
                        Отправить
                    </button>
                    <button
                        type="button"
                        disabled={isFormLocked}
                        onClick={resetForm}
                        className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-5 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        Сбросить
                    </button>
                </div>
            </form>
        </section>
    );
}
