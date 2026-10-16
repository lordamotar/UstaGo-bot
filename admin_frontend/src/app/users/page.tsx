'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { useDebounce } from '@/lib/useDebounce';
import { downloadCsv, fmtDate } from '@/lib/download';
import {
  ArrowLeft, Search, User as UserIcon, Phone, Activity, XCircle, Medal,
  CheckCircle, ShieldAlert, Briefcase, Download, Wallet, ShoppingBag, Gavel,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Pagination from '@/components/Pagination';
import { useMe } from '@/lib/useMe';

const TX_LABEL: Record<string, string> = {
  TOPUP: 'Пополнение', CONTACT_FEE: 'Оплата отклика', REFUND: 'Возврат', REFERRAL_BONUS: 'Реферальный бонус',
  RATING_BONUS: 'Бонус за рейтинг', WITHDRAWAL: 'Вывод', ADMIN_ADJUSTMENT: 'Корректировка',
};
const ORDER_LABEL: Record<string, string> = { NEW: 'Новый', ACTIVE: 'В работе', COMPLETED: 'Завершён', CANCELLED: 'Отменён' };
const BID_LABEL: Record<string, string> = { pending: 'Ожидает', accepted: 'Принят', rejected: 'Отклонён' };

export default function UsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const q = useDebounce(search);
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [onlyPending, setOnlyPending] = useState(false);
  const [sourceFilter, setSourceFilter] = useState('ALL');
  const [selectedUser, setSelectedUser] = useState<any | null>(null);
  const [exporting, setExporting] = useState(false);
  const router = useRouter();
  const { can } = useMe();

  const filterParams = useCallback(() => ({
    role: roleFilter !== 'ALL' ? roleFilter : undefined,
    q: q.trim() || undefined,
    master_status: onlyPending ? 'PENDING' : undefined,
    source: sourceFilter !== 'ALL' ? sourceFilter : undefined,
  }), [roleFilter, q, onlyPending, sourceFilter]);

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get('/users', { params: { ...filterParams(), skip, limit } });
      setUsers(res.data.items);
      setTotal(res.data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [filterParams, skip, limit]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);
  useEffect(() => { setSkip(0); }, [roleFilter, q, onlyPending, sourceFilter, limit]);
  // переход со страницы «Источники»: /users?source=...
  useEffect(() => {
    const s = new URLSearchParams(window.location.search).get('source');
    if (s) setSourceFilter(s);
  }, []);

  const openCard = async (id: number) => {
    try {
      setSelectedUser((await api.get(`/users/${id}`)).data);
    } catch { alert('Не удалось загрузить карточку'); }
  };

  const patchMaster = async (masterId: number, body: object, confirmText?: string) => {
    if (confirmText && !window.confirm(confirmText)) return;
    try {
      await api.patch(`/masters/${masterId}`, body);
      await fetchUsers();
      if (selectedUser) await openCard(selectedUser.id);
    } catch { alert('Ошибка обновления'); }
  };

  const adjustPoints = async () => {
    if (!selectedUser?.master_data) return;
    const raw = window.prompt('Сколько баллов начислить (отрицательное число — списать)?');
    if (!raw) return;
    const amount = parseInt(raw, 10);
    if (!amount) return alert('Нужно целое число, не 0');
    const description = window.prompt('Причина (увидит пользователь в истории)?', 'Корректировка администратором');
    if (!description) return;
    try {
      await api.post(`/masters/${selectedUser.master_data.master_id}/adjust-points`, { amount, description });
      await fetchUsers();
      await openCard(selectedUser.id);
    } catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка'); }
  };

  const exportCsv = async () => {
    try { setExporting(true); await downloadCsv('/users/export', filterParams(), 'users.csv'); }
    catch { alert('Ошибка экспорта'); }
    finally { setExporting(false); }
  };

  const m = selectedUser?.master_data;

  return (
    <div className="min-h-screen bg-background p-6 lg:p-10">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-3xl font-bold">Пользователи</h1>
        </div>
        <button onClick={exportCsv} disabled={exporting}
          className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 rounded-xl text-sm font-medium disabled:opacity-50">
          <Download className="w-4 h-4" /> {exporting ? 'Готовлю…' : 'Экспорт CSV'}
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-4 mb-8 items-center justify-between">
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input type="text" placeholder="Имя, @логин, телефон, ID или Telegram ID…" value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-secondary/50 border border-border rounded-xl py-2.5 pl-10 pr-4 focus:ring-2 focus:ring-primary outline-none" />
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex bg-secondary/50 p-1 rounded-xl border border-border">
            {['ALL', 'CLIENT', 'MASTER'].map((r) => (
              <button key={r} onClick={() => setRoleFilter(r)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${roleFilter === r ? 'bg-primary text-white shadow-lg' : 'hover:bg-background/50'}`}>
                {r === 'ALL' ? 'Все' : r === 'CLIENT' ? 'Клиенты' : 'Мастера'}
              </button>
            ))}
          </div>
          <button onClick={() => setOnlyPending(!onlyPending)}
            className={`px-4 py-2 rounded-xl text-sm font-medium border transition-all ${onlyPending ? 'bg-orange-500/20 border-orange-500/40 text-orange-400' : 'bg-secondary/50 border-border hover:bg-background/50'}`}>
            Ожидают проверки
          </button>
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}
            className="px-3 py-2 rounded-xl text-sm bg-secondary/50 border border-border outline-none">
            <option value="ALL">Все источники</option>
            <option value="referral">Приглашения друзей</option>
            <option value="direct">Напрямую</option>
            <option value="other">Другая ссылка</option>
            <option value="unknown">Неизвестно (до учёта)</option>
            {!['ALL', 'referral', 'direct', 'other', 'unknown'].includes(sourceFilter) && (
              <option value={sourceFilter}>{sourceFilter.startsWith('src:') ? `Кампания: ${sourceFilter.slice(4)}` : sourceFilter}</option>
            )}
          </select>
          <div className="flex bg-secondary/50 p-1 rounded-lg border border-border">
            {[10, 20, 50, 100].map((val) => (
              <button key={val} onClick={() => setLimit(val)}
                className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${limit === val ? 'bg-primary text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>
                {val}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="glass-card rounded-2xl overflow-hidden border border-border">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-secondary/30 border-b border-border">
              <tr>
                {['Пользователь', 'Роль', 'Контакты', 'Источник', 'Баллы', 'Мастер'].map((h) => (
                  <th key={h} className="px-6 py-4 text-sm font-semibold text-muted-foreground">{h}</th>
                ))}
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground text-right">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <AnimatePresence>
                {users.map((u) => (
                  <motion.tr key={u.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="hover:bg-secondary/20 transition-colors cursor-pointer" onClick={() => openCard(u.id)}>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${u.role === 'MASTER' ? 'bg-purple-500/10 text-purple-500' : 'bg-blue-500/10 text-blue-500'}`}>
                          {u.full_name?.[0] || '?'}
                        </div>
                        <div>
                          <p className="font-bold">{u.full_name}</p>
                          <p className="text-xs text-muted-foreground">ID: {u.id} · {fmtDate(u.created_at)}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${u.role === 'MASTER' ? 'bg-purple-500/10 text-purple-500' : u.role === 'ADMIN' ? 'bg-yellow-500/10 text-yellow-500' : 'bg-blue-500/10 text-blue-500'}`}>
                        {u.role === 'MASTER' ? 'Мастер' : u.role === 'ADMIN' ? 'Админ' : 'Клиент'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm font-medium">
                      {u.phone || <span className="text-muted-foreground">-</span>}
                      {u.username && <p className="text-xs text-muted-foreground">@{u.username}</p>}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      {u.source_label}
                      {u.referrer && <p className="text-xs text-muted-foreground">от {u.referrer.full_name || `ID ${u.referrer.id}`}</p>}
                    </td>
                    <td className="px-6 py-4 font-bold">{u.points}</td>
                    <td className="px-6 py-4">
                      {u.master_data ? (
                        <div>
                          <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold ${u.master_data.status === 'APPROVED' ? 'bg-green-500/10 text-green-500' : u.master_data.status === 'PENDING' ? 'bg-orange-500/10 text-orange-500' : 'bg-red-500/10 text-red-500'}`}>
                            {u.master_data.status}
                          </span>
                          <p className="text-xs text-muted-foreground mt-1 truncate max-w-[200px]">{u.master_data.categories?.join(', ') || 'Без категории'}</p>
                        </div>
                      ) : <span className="text-muted-foreground">-</span>}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button onClick={(e) => { e.stopPropagation(); openCard(u.id); }}
                        className="px-3 py-1.5 bg-secondary hover:bg-secondary/80 text-sm font-medium rounded-lg transition-colors">
                        Карточка
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
          {users.length === 0 && !loading && <div className="p-10 text-center text-muted-foreground">Пользователи не найдены</div>}
          {loading && <div className="p-10 flex justify-center"><div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary"></div></div>}
        </div>
        <Pagination total={total} limit={limit} skip={skip} onPageChange={setSkip} />
      </div>

      <AnimatePresence>
        {selectedUser && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedUser(null)}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-3xl bg-popover text-popover-foreground rounded-2xl shadow-2xl border border-border overflow-hidden max-h-[92vh] flex flex-col">
              <div className="p-6 border-b border-border flex items-center justify-between">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  {selectedUser.role === 'MASTER' ? <Briefcase className="text-purple-400" /> : <UserIcon className="text-blue-400" />}
                  {selectedUser.full_name}
                </h2>
                <button onClick={() => setSelectedUser(null)} className="p-2 hover:bg-secondary rounded-full">
                  <XCircle className="w-6 h-6 text-muted-foreground" />
                </button>
              </div>

              <div className="p-6 space-y-6 overflow-y-auto">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <Info label="Telegram" value={selectedUser.username ? `@${selectedUser.username}` : `id ${selectedUser.telegram_id}`} />
                  <Info label="Телефон" value={selectedUser.phone || 'Не указан'} icon={<Phone className="w-4 h-4 text-green-400" />} />
                  <Info label="Баллы" value={String(selectedUser.points)} icon={<Wallet className="w-4 h-4 text-primary" />} />
                  <Info label="Приглашено" value={String(selectedUser.referrals)} />
                  <Info label="Источник" value={selectedUser.source_label} />
                  <Info label="Пригласил" value={selectedUser.referrer ? (selectedUser.referrer.full_name || `ID ${selectedUser.referrer.id}`) : '—'} />
                </div>

                {m && (
                  <div className="border border-border p-4 rounded-xl space-y-3">
                    <h3 className="font-bold text-lg border-b border-border pb-2">Профиль мастера</h3>
                    <p className="text-sm"><span className="text-muted-foreground">Категории: </span>{m.categories?.join(', ') || 'Не указаны'}</p>
                    <p className="text-sm"><span className="text-muted-foreground">Районы: </span>{m.districts?.join(', ') || 'Все районы'}</p>
                    <p className="text-sm bg-secondary/50 p-3 rounded-lg">{m.description || 'Нет описания'}</p>
                    <div className="pt-3 border-t border-border flex flex-wrap items-center justify-between gap-3">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${m.status === 'APPROVED' ? 'bg-green-500/10 text-green-500' : m.status === 'PENDING' ? 'bg-orange-500/10 text-orange-500 animate-pulse' : 'bg-red-500/10 text-red-500'}`}>
                        Статус: {m.status}
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {can.moderate && m.status !== 'APPROVED' && (
                          <Btn color="green" onClick={() => patchMaster(m.master_id, { status: 'APPROVED' })}><CheckCircle className="w-4 h-4" />Одобрить</Btn>
                        )}
                        {can.moderate && m.status !== 'REJECTED' && (
                          <Btn color="red" onClick={() => patchMaster(m.master_id, { status: 'REJECTED' }, `Заблокировать мастера ${selectedUser.full_name}?`)}><ShieldAlert className="w-4 h-4" />Бан</Btn>
                        )}
                        {can.moderate && <Btn color={m.is_accredited ? 'yellow' : 'gray'} onClick={() => patchMaster(m.master_id, { is_accredited: !m.is_accredited })}>
                          <Medal className="w-4 h-4" />{m.is_accredited ? 'Аккредитован' : 'Выдать аккредитацию'}
                        </Btn>}
                        {can.finance && <Btn color="gray" onClick={adjustPoints}><Wallet className="w-4 h-4" />Баллы</Btn>}
                      </div>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-primary/5 border border-primary/20 p-4 rounded-xl text-center">
                    <p className="text-sm text-muted-foreground mb-1">Заказов как клиент</p>
                    <p className="text-3xl font-black">{selectedUser.client_orders_count}</p>
                  </div>
                  <div className="bg-purple-500/5 border border-purple-500/20 p-4 rounded-xl text-center">
                    <p className="text-sm text-muted-foreground mb-1">Принято откликов</p>
                    <p className="text-3xl font-black text-purple-400">
                      {m ? m.processed_orders : '—'} <span className="text-lg text-muted-foreground font-normal">{m ? `/ ${m.total_bids}` : ''}</span>
                    </p>
                  </div>
                </div>

                <Section icon={<Activity className="w-4 h-4" />} title="История баллов" empty={!selectedUser.transactions.length}>
                  {selectedUser.transactions.map((t: any) => (
                    <Row key={t.id} left={`${TX_LABEL[t.type] || t.type}${t.description ? ' — ' + t.description : ''}`} date={t.date}
                      right={<span className={t.amount > 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>{t.amount > 0 ? '+' : ''}{t.amount}</span>} />
                  ))}
                </Section>
                <Section icon={<ShoppingBag className="w-4 h-4" />} title="Последние заказы" empty={!selectedUser.orders.length}>
                  {selectedUser.orders.map((o: any) => (
                    <Row key={o.id} left={`№${o.id} · ${o.category}`} date={o.created_at} right={<span className="text-xs font-bold">{ORDER_LABEL[o.status] || o.status}</span>} />
                  ))}
                </Section>
                {m && (
                  <Section icon={<Gavel className="w-4 h-4" />} title="Последние отклики" empty={!selectedUser.bids.length}>
                    {selectedUser.bids.map((b: any) => (
                      <Row key={b.id} left={`Заказ №${b.order_id}${b.price ? ` · ${b.price} ₸` : ''}`} date={b.created_at}
                        right={<span className="text-xs font-bold">{BID_LABEL[b.status] || b.status}</span>} />
                    ))}
                  </Section>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Info({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="bg-secondary/30 p-3 rounded-xl">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className="font-bold flex items-center gap-1.5 break-all">{icon}{value}</p>
    </div>
  );
}

function Btn({ color, onClick, children }: { color: 'green' | 'red' | 'yellow' | 'gray'; onClick: () => void; children: React.ReactNode }) {
  const c = {
    green: 'bg-green-500/10 hover:bg-green-500/20 text-green-500',
    red: 'bg-red-500/10 hover:bg-red-500/20 text-red-500',
    yellow: 'bg-yellow-500/20 text-yellow-500',
    gray: 'bg-secondary text-muted-foreground hover:bg-secondary/80',
  }[color];
  return <button onClick={onClick} className={`px-3 py-1.5 flex items-center gap-1 text-sm font-bold rounded-lg transition-colors ${c}`}>{children}</button>;
}

function Section({ icon, title, empty, children }: { icon: React.ReactNode; title: string; empty: boolean; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="font-bold mb-2 flex items-center gap-2 text-sm text-muted-foreground">{icon}{title}</h3>
      {empty ? <p className="text-sm text-muted-foreground bg-secondary/20 p-3 rounded-xl text-center">Пока пусто</p>
        : <div className="divide-y divide-border border border-border rounded-xl max-h-56 overflow-y-auto">{children}</div>}
    </div>
  );
}

function Row({ left, right, date }: { left: string; right: React.ReactNode; date: string }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
      <div className="min-w-0"><p className="truncate">{left}</p><p className="text-xs text-muted-foreground">{fmtDate(date)}</p></div>
      <div className="shrink-0">{right}</div>
    </div>
  );
}
