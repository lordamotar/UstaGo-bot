'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { ArrowLeft, Link2, Copy, Check, Megaphone, UserPlus } from 'lucide-react';

const PERIODS = [
  { days: 7, label: '7 дн.' },
  { days: 30, label: '30 дн.' },
  { days: 90, label: '90 дн.' },
  { days: 0, label: 'Всё время' },
];

export default function AcquisitionPage() {
  const router = useRouter();
  const [days, setDays] = useState(30);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tag, setTag] = useState('');
  const [link, setLink] = useState<{ link: string; source: string } | null>(null);
  const [linkError, setLinkError] = useState('');
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get('/stats/acquisition', { params: { days } });
      setData(r.data);
    } catch (e) { console.error(e); setData(null); }
    finally { setLoading(false); }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  const makeLink = async () => {
    setLinkError(''); setLink(null); setCopied(false);
    try {
      const r = await api.get('/stats/acquisition/link', { params: { tag } });
      setLink(r.data);
    } catch (e: any) {
      setLinkError(e.response?.data?.detail || 'Не удалось создать ссылку');
    }
  };

  const copy = async () => {
    if (!link) return;
    try { await navigator.clipboard.writeText(link.link); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* буфер недоступен */ }
  };

  const sources: any[] = data?.sources ?? [];
  const max = Math.max(1, ...sources.map((s) => s.users));
  const toUsers = (source: string) => router.push(`/users?source=${encodeURIComponent(source)}`);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <div className="flex items-center gap-4">
          <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <div>
            <h1 className="text-3xl font-extrabold">Источники пользователей</h1>
            <p className="text-muted-foreground text-sm">Откуда приходят люди и кто их приводит</p>
          </div>
        </div>
        <div className="flex bg-secondary/50 p-1 rounded-xl border border-border">
          {PERIODS.map((p) => (
            <button key={p.days} onClick={() => setDays(p.days)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-all ${days === p.days ? 'bg-primary text-white shadow-lg' : 'hover:bg-background/50'}`}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="glass-card p-6 rounded-2xl mb-8">
        <h2 className="text-lg font-bold flex items-center gap-2 mb-1"><Megaphone className="w-5 h-5 text-primary" />Ссылка для рекламы</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Придумайте метку (например, <code>instagram</code> или <code>flyer_almaty</code>) и разместите ссылку в рекламе, посте или на листовке:
          все, кто придёт по ней, будут посчитаны отдельно.
        </p>
        <div className="flex flex-wrap gap-3">
          <input value={tag} onChange={(e) => setTag(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && tag.trim() && makeLink()}
            placeholder="Метка, латиницей" maxLength={60}
            className="flex-1 min-w-[220px] bg-secondary/50 border border-border rounded-xl px-4 py-2 outline-none focus:border-primary" />
          <button onClick={makeLink} disabled={!tag.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 disabled:opacity-50 text-white rounded-xl transition-all">
            <Link2 className="w-4 h-4" />Создать ссылку
          </button>
        </div>
        {linkError && <p className="text-sm text-red-400 mt-3">{linkError}</p>}
        {link && (
          <div className="mt-4 flex flex-wrap items-center gap-3 bg-secondary/30 rounded-xl p-3">
            <code className="text-sm break-all flex-1">{link.link}</code>
            <button onClick={copy} className="flex items-center gap-1 px-3 py-1.5 bg-secondary hover:bg-secondary/80 text-sm rounded-lg">
              {copied ? <><Check className="w-4 h-4 text-green-400" />Скопировано</> : <><Copy className="w-4 h-4" />Копировать</>}
            </button>
          </div>
        )}
      </div>

      <div className="glass-card p-6 rounded-2xl mb-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold">Откуда пришли</h2>
          {data && <span className="text-sm text-muted-foreground">Новых пользователей: <b className="text-foreground">{data.total_new}</b></span>}
        </div>
        {loading ? <p className="text-muted-foreground text-sm">Загрузка…</p>
          : sources.length === 0 ? <p className="text-muted-foreground text-sm">За выбранный период новых пользователей нет</p> : (
          <div className="space-y-5">
            {sources.map((s) => (
              <div key={s.source} onClick={() => toUsers(s.source)} className="cursor-pointer group">
                <div className="flex flex-wrap justify-between gap-2 text-sm mb-1">
                  <span className="font-medium group-hover:text-primary transition-colors">{s.label}</span>
                  <span><b>{s.users}</b> <span className="text-muted-foreground text-xs">{s.share}% · мастеров {s.masters} (одобрено {s.approved_masters}) · с заявкой {s.with_orders} ({s.order_rate}%)</span></span>
                </div>
                <div className="h-3 bg-secondary/50 rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${(s.users / max) * 100}%` }} />
                </div>
              </div>
            ))}
            <p className="text-xs text-muted-foreground">Нажмите на источник, чтобы открыть этих пользователей. «Неизвестно» — те, кто пришёл до начала учёта.</p>
          </div>
        )}
      </div>

      <div className="glass-card p-6 rounded-2xl">
        <h2 className="text-lg font-bold flex items-center gap-2 mb-4"><UserPlus className="w-5 h-5 text-primary" />Кто больше всех приглашает</h2>
        {!data || data.top_referrers.length === 0 ? <p className="text-muted-foreground text-sm">Приглашений за период нет</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="border-b border-border">
                <tr>{['Пригласивший', 'Приглашено', 'Из них мастеров', 'Мастеров одобрено'].map((h) => (
                  <th key={h} className="px-4 py-3 text-sm font-semibold text-muted-foreground">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.top_referrers.map((r: any) => (
                  <tr key={r.user_id} className="hover:bg-secondary/20 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-bold">{r.full_name || `ID ${r.user_id}`}</p>
                      {r.username && <p className="text-xs text-muted-foreground">@{r.username}</p>}
                    </td>
                    <td className="px-4 py-3 font-bold">{r.invited}</td>
                    <td className="px-4 py-3">{r.masters}</td>
                    <td className="px-4 py-3">{r.approved_masters}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
