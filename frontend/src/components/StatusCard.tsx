import type { CTOAISnapshot } from '../types';

const STATE_LABELS: Record<string, string> = {
    idle: 'В ожидании',
    scanning: 'Сканирует рынок',
    evaluating: 'Оценивает гипотезы',
    awaiting_risk: 'Ждёт риск-отчёт',
    awaiting_execution: 'Ждёт исполнение',
    managing_position: 'Сопровождает позицию',
    emergency_stop: 'Аварийная остановка',
};

type Props = {
    snapshot: CTOAISnapshot;
};

export function StatusCard({ snapshot }: Props) {
    const stateLabel = STATE_LABELS[snapshot.state] ?? snapshot.state;
    const confidencePct = Math.round(snapshot.confidence * 100);

    return (
        <div className="grid gap-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card md:grid-cols-3">
            <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-indigo-300">Текущий режим</h3>
                <p className="mt-1 text-2xl font-semibold text-white">{snapshot.mode}</p>
            </div>
            <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-indigo-300">Состояние</h3>
                <p className="mt-1 text-xl text-slate-200">{stateLabel}</p>
            </div>
            <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-indigo-300">Уверенность</h3>
                <div className="mt-2 h-2 rounded-full bg-slate-800">
                    <div
                        className="h-full rounded-full bg-emerald-400"
                        style={{ width: `${confidencePct}%`, transition: 'width 0.3s ease-in-out' }}
                    />
                </div>
                <p className="mt-1 text-sm text-slate-300">{confidencePct}%</p>
            </div>
        </div>
    );
}
