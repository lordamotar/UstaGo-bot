'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { useDebounce } from '@/lib/useDebounce';
import { fmtDate } from '@/lib/download';
import { useMe } from '@/lib/useMe';
import Pagination from '@/components/Pagination';
import { ArrowLeft, Search, LifeBuoy, Send, CheckCircle2, XCircle } from 'lucide-react';

const TABS = [
  { id: 'open', label: 'Без ответа' },
  { id: 'answered', label: 'Отвечено' },
  { id: 'all', label: 'Все' },
];

export default function SupportPage() {
  const router = useRouter();
  const { can } = useMe();
  const [tab, setTab] = useState('open');
  const [search, setSearch] = useState('');
  const q = useDebounce(search);
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [openCount, setOpenCount] = useState(0);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [sending, setSending] = useState<number | null>(null);
  const [closing, setClosing] = useState(false);
  const [confirmAll, setConfirmAll] = useState(false);
  const limit = 20;

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get('/support/tickets', { params: { status: tab, q: q.trim() || undefined, skip, limit } });
      setItems(r.data.items);
      setTotal(r.data.total);
      setOpenCount(r.data.open_count);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [tab, q, skip]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSkip(0); }, [tab, q]);

  const reply = async (id: number) => {
    const text = (drafts[id] || '').trim();
    if (!text) return;
    try {
      setSending(id);
      await api.post(`/support/tickets/${id}/reply`, { text });
      setDrafts((d) => { const n = { ...d }; delete n[id]; return n; });
      await load();
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Не удалось отправить ответ');
    } finally { setSending(null); }
  };

  // закрыть без ответа: человеку уже ответили (например, прямо в Telegram)
  const closeTickets = async (ids?: number[]) => {
    try {
      setClosing(true);
      await api.post('/support/tickets/close', ids ? { ids } : {});
      setConfirmAll(false);
      await load();
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Не удалось закрыть');
    } finally { setClosing(false); }
  };

  return (
    <div className="min-h-screen bg-background p-6 lg:p-10">
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors"><ArrowLeft className="w-6 h-6" /></button>
        <h1 className="text-3xl font-bold flex items-center gap-2"><LifeBuoy className="w-7 h-7 text-primary" />Поддержка</h1>
        {can.moderate && openCount > 0 && (
          <div className="ml-auto flex items-center gap-2">
            {confirmAll ? (
              <>
                <span className="text-sm text-muted-foreground">Закрыть все ({openCount}) без ответа?</span>
                <button onClick={() => closeTickets()} disabled={closing}
                  className="px-3 py-2 bg-red-500/90 hover:bg-red-500 text-white text-sm font-bold rounded-xl disabled:opacity-50">{closing ? 'Закрываю…' : 'Да, закрыть'}</button>
                <button onClick={() => setConfirmAll(false)} className="px-3 py-2 bg-secondary hover:bg-secondary/80 text-sm rounded-xl">Отмена</button>
              </>
            ) : (
              <button onClick={() => setConfirmAll(true)}
                className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 text-sm font-medium rounded-xl transition-colors">
                <XCircle className="w-4 h-4" />Закрыть все без ответа
              </button>
            )}
          </div>
        )}
      </div>

      <div className="flex flex-col md:flex-row gap-4 mb-8 items-center">
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input type="text" placeholder="Текст обращения, имя, @логин или телефон…" value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-secondary/50 border border-border rounded-xl py-2.5 pl-10 pr-4 focus:ring-2 focus:ring-primary outline-none" />
        </div>
        <div className="flex bg-secondary/50 p-1 rounded-xl border border-border">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${tab === t.id ? 'bg-primary text-white shadow-lg' : 'hover:bg-background/50'}`}>
              {t.label}{t.id === 'open' && openCount > 0 && <span className="ml-2 px-1.5 rounded-full bg-orange-500 text-white text-[10px] font-bold">{openCount}</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        {items.map((t) => (
          <div key={t.id} className="glass-card rounded-2xl border border-border p-5">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div>
                <p className="font-bold">{t.user.name} <span className="text-xs text-muted-foreground font-normal">#{t.id} · {t.user.role === 'MASTER' ? 'мастер' : 'клиент'}</span></p>
                <p className="text-xs text-muted-foreground">
                  {t.user.username ? `@${t.user.username} · ` : ''}{t.user.phone || 'телефон не указан'} · {fmtDate(t.created_at)}
                </p>
              </div>
              {t.is_replied && (t.closed_without_reply
                ? <span className="flex items-center gap-1 text-xs font-bold text-muted-foreground"><XCircle className="w-4 h-4" />Закрыто без ответа {fmtDate(t.replied_at)}</span>
                : <span className="flex items-center gap-1 text-xs font-bold text-green-400"><CheckCircle2 className="w-4 h-4" />Отвечено {fmtDate(t.replied_at)}</span>)}
            </div>
            <p className="whitespace-pre-wrap bg-secondary/30 rounded-xl p-4 text-sm">{t.message}</p>

            {t.is_replied ? (
              t.admin_reply && <p className="whitespace-pre-wrap border-l-2 border-primary pl-4 mt-3 text-sm text-muted-foreground">{t.admin_reply}</p>
            ) : can.moderate ? (
              <div className="mt-3 flex gap-3 items-end">
                <textarea value={drafts[t.id] || ''} onChange={(e) => setDrafts({ ...drafts, [t.id]: e.target.value })} rows={2} maxLength={3500}
                  placeholder="Ответ пользователю (придёт в Telegram от имени бота)…"
                  className="flex-1 bg-secondary/50 border border-border rounded-xl p-3 text-sm outline-none focus:ring-2 focus:ring-primary resize-y" />
                <button onClick={() => reply(t.id)} disabled={sending === t.id || !(drafts[t.id] || '').trim()}
                  className="px-4 py-2.5 flex items-center gap-2 bg-primary hover:bg-primary/90 text-white font-bold rounded-xl disabled:opacity-50">
                  <Send className="w-4 h-4" />{sending === t.id ? 'Отправка…' : 'Ответить'}
                </button>
                <button onClick={() => closeTickets([t.id])} disabled={closing} title="Закрыть, ничего не отправляя пользователю"
                  className="px-4 py-2.5 flex items-center gap-2 bg-secondary hover:bg-secondary/80 text-sm font-medium rounded-xl disabled:opacity-50">
                  <XCircle className="w-4 h-4" />Закрыть
                </button>
              </div>
            ) : <p className="text-xs text-muted-foreground mt-3">Отвечать могут суперадмин и модератор.</p>}
          </div>
        ))}
        {!loading && items.length === 0 && <div className="glass-card rounded-2xl border border-border p-10 text-center text-muted-foreground">Обращений нет</div>}
        {loading && <div className="p-10 flex justify-center"><div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary"></div></div>}
      </div>
      <div className="mt-6 glass-card rounded-2xl overflow-hidden border border-border">
        <Pagination total={total} limit={limit} skip={skip} onPageChange={setSkip} />
      </div>
    </div>
  );
}
