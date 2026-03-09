import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useMemo, useState } from 'react';
import { submitManualDirective } from '../api';
const DEFAULT_FORM = {
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
const TIME_IN_FORCE_OPTIONS = [
    { value: 'GTC', label: 'GTC' },
    { value: 'IOC', label: 'IOC' },
    { value: 'FOK', label: 'FOK' },
];
export function ManualTradePanel({ onNotify, disabled = false, modeLabel }) {
    const [form, setForm] = useState(DEFAULT_FORM);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);
    const isLimitOrder = form.order_type === 'limit';
    const isOpenAction = form.action === 'open';
    const isFormLocked = disabled || submitting;
    const updateForm = useCallback((patch) => {
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
    const handleSubmit = useCallback(async (event) => {
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
        const payload = {
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
        }
        else {
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
        }
        catch (err) {
            const message = err instanceof Error ? err.message : 'Не удалось отправить команду';
            setError(message);
            onNotify(message);
        }
        finally {
            setSubmitting(false);
        }
    }, [form, isLimitOrder, isOpenAction, onNotify, parsedQuantity, parsedPrice, parsedTP, parsedSL, resetForm]);
    const handleActionChange = useCallback((nextAction) => {
        updateForm({
            action: nextAction,
            reduce_only: nextAction === 'close' ? true : form.reduce_only,
            take_profit_price: nextAction === 'open' ? form.take_profit_price : '',
            stop_loss_price: nextAction === 'open' ? form.stop_loss_price : '',
        });
    }, [form.reduce_only, form.stop_loss_price, form.take_profit_price, updateForm]);
    return (_jsxs("section", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card", children: [_jsxs("div", { className: "flex flex-col gap-2 md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { children: [_jsx("h2", { className: "text-lg font-semibold text-white", children: "\u0420\u0443\u0447\u043D\u043E\u0435 \u0443\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u0435" }), _jsx("p", { className: "text-sm text-slate-400", children: "\u0424\u043E\u0440\u043C\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0438\u0433\u043D\u0430\u043B\u044B \u0432\u0440\u0443\u0447\u043D\u0443\u044E \u2014 \u043E\u043D\u0438 \u0441\u0440\u0430\u0437\u0443 \u043F\u043E\u043F\u0430\u0434\u0430\u044E\u0442 \u0432 Execution Engine." })] }), _jsxs("div", { className: "flex items-center gap-3 text-xs text-slate-500", children: [disabled && _jsxs("span", { children: ["\u0414\u043E\u0441\u0442\u0443\u043F\u043D\u043E \u0442\u043E\u043B\u044C\u043A\u043E \u0432 \u0440\u0443\u0447\u043D\u043E\u043C \u0440\u0435\u0436\u0438\u043C\u0435", modeLabel ? ` (${modeLabel})` : ''] }), submitting && _jsx("span", { children: "\u041E\u0442\u043F\u0440\u0430\u0432\u043A\u0430 \u0437\u0430\u044F\u0432\u043A\u0438\u2026" })] })] }), _jsxs("form", { className: "mt-6 space-y-5", onSubmit: handleSubmit, children: [_jsxs("fieldset", { disabled: isFormLocked, className: "grid gap-4 md:grid-cols-2 lg:grid-cols-3", children: [_jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u0422\u0438\u043A\u0435\u0440", _jsx("input", { type: "text", value: form.symbol, onChange: (event) => updateForm({ symbol: event.target.value.toUpperCase() }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40", placeholder: "\u043D\u0430\u043F\u0440\u0438\u043C\u0435\u0440, BTCUSDT" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u041E\u0431\u044A\u0451\u043C", _jsx("input", { type: "number", step: "0.001", min: "0", value: form.quantity, onChange: (event) => updateForm({ quantity: event.target.value }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u041D\u0430\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u0435", _jsxs("select", { value: form.direction, onChange: (event) => updateForm({ direction: event.target.value }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40", children: [_jsx("option", { value: "long", children: "\u041B\u043E\u043D\u0433" }), _jsx("option", { value: "short", children: "\u0428\u043E\u0440\u0442" })] })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435", _jsxs("select", { value: form.action, onChange: (event) => handleActionChange(event.target.value), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40", children: [_jsx("option", { value: "open", children: "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043F\u043E\u0437\u0438\u0446\u0438\u044E" }), _jsx("option", { value: "close", children: "\u0417\u0430\u043A\u0440\u044B\u0442\u044C \u043F\u043E\u0437\u0438\u0446\u0438\u044E" })] })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u0422\u0438\u043F \u043E\u0440\u0434\u0435\u0440\u0430", _jsxs("select", { value: form.order_type, onChange: (event) => updateForm({
                                            order_type: event.target.value,
                                            price: event.target.value === 'limit' ? form.price : '',
                                        }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40", children: [_jsx("option", { value: "market", children: "Market" }), _jsx("option", { value: "limit", children: "Limit" })] })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u0426\u0435\u043D\u0430 (\u0434\u043B\u044F Limit)", _jsx("input", { type: "number", step: "0.01", min: "0", value: form.price, onChange: (event) => updateForm({ price: event.target.value }), disabled: !isLimitOrder, className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/70" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u041F\u043B\u0435\u0447\u043E", _jsx("input", { type: "number", step: "0.1", min: "0", value: form.leverage, onChange: (event) => updateForm({ leverage: event.target.value }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["Time-in-force", _jsx("select", { value: form.time_in_force, onChange: (event) => updateForm({ time_in_force: event.target.value }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40", children: TIME_IN_FORCE_OPTIONS.map((option) => (_jsx("option", { value: option.value, children: option.label }, option.value))) })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u0423\u0432\u0435\u0440\u0435\u043D\u043D\u043E\u0441\u0442\u044C (0-1)", _jsx("input", { type: "number", step: "0.01", min: "0", max: "1", value: form.confidence, onChange: (event) => updateForm({ confidence: event.target.value }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u0421\u0440\u043E\u043A \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044F (\u043C\u0438\u043D)", _jsx("input", { type: "number", min: "0", step: "1", value: form.expires_in_minutes, onChange: (event) => updateForm({ expires_in_minutes: event.target.value }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex items-center gap-3 text-sm text-slate-300", children: [_jsx("input", { type: "checkbox", checked: form.reduce_only || !isOpenAction, disabled: !isOpenAction || isFormLocked, onChange: (event) => updateForm({ reduce_only: event.target.checked }), className: "h-4 w-4 rounded border border-slate-600 bg-slate-900 text-indigo-500 focus:ring-2 focus:ring-indigo-500" }), "Reduce only"] })] }), isOpenAction && (_jsxs("fieldset", { disabled: isFormLocked, className: "grid gap-4 md:grid-cols-2", children: [_jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u0422\u0435\u0439\u043A-\u043F\u0440\u043E\u0444\u0438\u0442", _jsx("input", { type: "number", step: "0.01", min: "0", value: form.take_profit_price, onChange: (event) => updateForm({ take_profit_price: event.target.value }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-sm text-slate-300", children: ["\u0421\u0442\u043E\u043F-\u043B\u043E\u0441\u0441", _jsx("input", { type: "number", step: "0.01", min: "0", value: form.stop_loss_price, onChange: (event) => updateForm({ stop_loss_price: event.target.value }), className: "rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] })] })), error && _jsx("p", { className: "text-sm text-rose-400", children: error })] })] }));
}
