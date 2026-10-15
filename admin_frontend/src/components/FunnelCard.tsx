'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import { Filter } from 'lucide-react';

export default function FunnelCard() {
  const [days, setDays] = useState(30);
  const [f, setF] = useState<any>(null);

  useEffect(() => {
    api.get('/stats/funnel', { params: { days } }).then((r) => setF(r.data)).catch(() => setF(null));
  }, [days]);

  const steps = f ? [
    { name: 'Заявок создано', value: f.created, note: '' },
    { name: 'Получили отклик', value: f.with_bids, note: `${f.bid_rate}% от заявок` },
    { name: 'Мастер выбран', value: f.accepted, note: `${f.accept_rate}% от получивших отклик` },
    { name: 'Завершены', value: f.completed, note: `${f.completion_rate}% от выбранных` },
  ] : [];
  const max = Math.max(1, ...steps.map((s) => s.value));

  return (
    <div className="glass-card p-6 rounded-2xl mb-10">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h2 className="text-xl font-bold flex items-center gap-2"><Filter className="w-5 h-5 text-primary" />Воронка заявок</h2>
        <div className="flex bg-secondary/50 p-1 rounded-xl border border-border">
          {[7, 30, 90].map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-all ${days === d ? 'bg-primary text-white shadow-lg' : 'hover:bg-background/50'}`}>
              {d} дн.
            </button>
          ))}
        </div>
      </div>
      {!f ? <p className="text-muted-foreground text-sm">Нет данных</p> : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-4">
            {steps.map((s) => (
              <div key={s.name}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium">{s.name}</span>
                  <span><b>{s.value}</b> <span className="text-muted-foreground text-xs">{s.note}</span></span>
                </div>
                <div className="h-3 bg-secondary/50 rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${(s.value / max) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-1 gap-3">
            <Metric label="Без откликов" value={f.no_response} warn={f.no_response > 0} hint="заявки, которые никто не взял" />
            <Metric label="Первый отклик (медиана)" value={f.median_first_bid_minutes == null ? '—' : f.median_first_bid_minutes < 90 ? `${f.median_first_bid_minutes} мин` : `${(f.median_first_bid_minutes / 60).toFixed(1)} ч`} />
            <Metric label="Активных мастеров" value={f.active_masters} hint="сделали хотя бы один отклик" />
            <Metric label="Отменено" value={f.cancelled} />
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, hint, warn }: { label: string; value: string | number; hint?: string; warn?: boolean }) {
  return (
    <div className="bg-secondary/30 rounded-xl p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-2xl font-black ${warn ? 'text-orange-400' : ''}`}>{value}</p>
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}
