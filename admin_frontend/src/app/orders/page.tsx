'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { useDebounce } from '@/lib/useDebounce';
import { downloadCsv, fmtDate } from '@/lib/download';
import { ArrowLeft, Search, ShoppingBag, MapPin, Calendar, DollarSign, AlertCircle, Download, Ban } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Pagination from '@/components/Pagination';
import { useMe } from '@/lib/useMe';

const STATUS_NAME: Record<string, string> = { NEW: 'Новый', ACTIVE: 'В работе', COMPLETED: 'Завершён', CANCELLED: 'Отменён' };
const STATUS_COLOR: Record<string, string> = {
  NEW: 'bg-blue-500/10 text-blue-500', ACTIVE: 'bg-yellow-500/10 text-yellow-500',
  COMPLETED: 'bg-green-500/10 text-green-500', CANCELLED: 'bg-red-500/10 text-red-500',
};
const BID_NAME: Record<string, string> = { pending: 'Ожидает', accepted: 'Принят', rejected: 'Отклонён' };

export default function OrdersPage() {
  const [orders, setOrders] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const q = useDebounce(search);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [categoryId, setCategoryId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [categories, setCategories] = useState<any[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<any | null>(null);
  const [exporting, setExporting] = useState(false);
  const router = useRouter();
  const { can } = useMe();

  useEffect(() => {
    api.get('/categories').then((r) => setCategories(r.data.items)).catch(() => {});
  }, []);

  const filterParams = useCallback(() => ({
    status: statusFilter !== 'ALL' ? statusFilter : undefined,
    q: q.trim() || undefined,
    category_id: categoryId || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }), [statusFilter, q, categoryId, dateFrom, dateTo]);

  const fetchOrders = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get('/orders', { params: { ...filterParams(), skip, limit } });
      setOrders(res.data.items);
      setTotal(res.data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [filterParams, skip, limit]);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);
  useEffect(() => { setSkip(0); }, [statusFilter, q, categoryId, dateFrom, dateTo, limit]);

  const openOrder = async (id: number) => {
    try { setSelectedOrder((await api.get(`/orders/${id}`)).data); }
    catch { alert('Ошибка при загрузке заявки'); }
  };

  const cancelOrder = async () => {
    if (!selectedOrder) return;
    const n = selectedOrder.bids.filter((b: any) => b.status !== 'rejected').length;
    if (!window.confirm(`Отменить заказ №${selectedOrder.id}?\nКлиент и мастера получат уведомление, ${n} мастер(ам) вернутся баллы за отклик.`)) return;
    try {
      await api.post(`/orders/${selectedOrder.id}/cancel`);
      await Promise.all([openOrder(selectedOrder.id), fetchOrders()]);
    } catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка отмены'); }
  };

  const exportCsv = async () => {
    try { setExporting(true); await downloadCsv('/orders/export', filterParams(), 'orders.csv'); }
    catch { alert('Ошибка экспорта'); }
    finally { setExporting(false); }
  };

  const canCancel = can.moderate && selectedOrder && ['NEW', 'ACTIVE'].includes(selectedOrder.status);

  return (
    <div className="min-h-screen bg-background p-6 lg:p-10">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-3xl font-bold">Управление заказами</h1>
        </div>
        <button onClick={exportCsv} disabled={exporting}
          className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 rounded-xl text-sm font-medium disabled:opacity-50">
          <Download className="w-4 h-4" /> {exporting ? 'Готовлю…' : 'Экспорт CSV'}
        </button>
      </div>

      <div className="flex flex-col gap-4 mb-8">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input type="text" placeholder="№ заказа, текст заявки, категория, район, клиент или телефон…" value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-secondary/50 border border-border rounded-xl py-2.5 pl-10 pr-4 focus:ring-2 focus:ring-primary outline-none" />
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex bg-secondary/50 p-1 rounded-xl border border-border overflow-x-auto">
            {['ALL', 'NEW', 'ACTIVE', 'COMPLETED', 'CANCELLED'].map((s) => (
              <button key={s} onClick={() => setStatusFilter(s)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${statusFilter === s ? 'bg-primary text-white shadow-lg' : 'hover:bg-background/50'}`}>
                {s === 'ALL' ? 'Все' : STATUS_NAME[s]}
              </button>
            ))}
          </div>
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}
            className="bg-secondary/50 border border-border rounded-xl px-3 py-2 text-sm outline-none">
            <option value="">Все категории</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <div className="flex items-center gap-2 text-sm">
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
              className="bg-secondary/50 border border-border rounded-xl px-3 py-2 outline-none" />
            <span className="text-muted-foreground">—</span>
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
              className="bg-secondary/50 border border-border rounded-xl px-3 py-2 outline-none" />
          </div>
          <div className="flex bg-secondary/50 p-1 rounded-lg border border-border ml-auto">
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
                {['№ / Дата', 'Статус', 'Категория / Район', 'Клиент', 'Бюджет', 'Отклики'].map((h) => (
                  <th key={h} className="px-6 py-4 text-sm font-semibold text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <AnimatePresence>
                {orders.map((o) => (
                  <motion.tr key={o.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="hover:bg-secondary/20 transition-colors cursor-pointer" onClick={() => openOrder(o.id)}>
                    <td className="px-6 py-4">
                      <span className="font-bold"># {o.id}</span>
                      <span className="text-xs text-muted-foreground flex items-center gap-1 mt-1"><Calendar className="w-3 h-3" />{fmtDate(o.created_at)}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${STATUS_COLOR[o.status] || 'bg-secondary'}`}>{STATUS_NAME[o.status] || o.status}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-bold">{o.category}</span>
                      <span className="text-xs text-muted-foreground flex items-center gap-1 mt-1"><MapPin className="w-3 h-3" />{o.district || 'Весь город'}</span>
                    </td>
                    <td className="px-6 py-4 text-sm">{o.client_name}</td>
                    <td className="px-6 py-4 text-sm">{o.budget ? `${o.budget} ₸` : '—'}</td>
                    <td className="px-6 py-4">
                      <span className={`font-bold ${o.bids_count === 0 && o.status === 'NEW' ? 'text-orange-400' : ''}`}>{o.bids_count}</span>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
          {orders.length === 0 && !loading && <div className="p-10 text-center text-muted-foreground">Заказы не найдены</div>}
          {loading && <div className="p-10 flex justify-center"><div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary"></div></div>}
        </div>
        <Pagination total={total} limit={limit} skip={skip} onPageChange={setSkip} />
      </div>

      <AnimatePresence>
        {selectedOrder && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedOrder(null)}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-2xl bg-popover text-popover-foreground rounded-2xl shadow-2xl border border-border overflow-hidden max-h-[90vh] flex flex-col">
              <div className="p-6 border-b border-border flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold flex items-center gap-2"><ShoppingBag className="text-orange-400" />Заказ #{selectedOrder.id}</h2>
                  <p className="text-sm text-muted-foreground mt-1">{selectedOrder.category} · {selectedOrder.district || 'Весь город'} · {fmtDate(selectedOrder.created_at)}</p>
                </div>
                <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${STATUS_COLOR[selectedOrder.status] || 'bg-secondary'}`}>{STATUS_NAME[selectedOrder.status] || selectedOrder.status}</span>
              </div>

              <div className="p-6 overflow-y-auto space-y-6">
                <div>
                  <h3 className="text-sm font-bold text-muted-foreground mb-2">Описание задачи</h3>
                  <div className="bg-secondary/30 p-4 rounded-xl border border-border"><p className="whitespace-pre-wrap">{selectedOrder.description}</p></div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-secondary/30 p-4 rounded-xl border border-border">
                    <p className="text-sm text-muted-foreground mb-1">Клиент</p>
                    <p className="font-bold">{selectedOrder.client.name}</p>
                    <p className="text-xs text-primary mt-1">{selectedOrder.client.phone || 'нет телефона'}</p>
                  </div>
                  <div className="bg-secondary/30 p-4 rounded-xl border border-border">
                    <p className="text-sm text-muted-foreground mb-1">Ориентир бюджета</p>
                    <p className="font-bold flex items-center gap-2"><DollarSign className="w-4 h-4 text-green-400" />{selectedOrder.budget ? `${selectedOrder.budget} ₸` : 'Не указан'}</p>
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-bold text-muted-foreground mb-3 flex items-center gap-2"><AlertCircle className="w-4 h-4" />Отклики мастеров ({selectedOrder.bids.length})</h3>
                  {selectedOrder.bids.length > 0 ? (
                    <div className="space-y-3">
                      {selectedOrder.bids.map((bid: any) => (
                        <div key={bid.id} className="p-4 bg-secondary/20 border border-border rounded-xl">
                          <div className="flex items-center justify-between mb-2">
                            <p className="font-bold text-primary">{bid.master_name} <span className="text-xs text-muted-foreground font-normal">{fmtDate(bid.created_at)}</span></p>
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-md ${bid.status === 'accepted' ? 'bg-green-500/20 text-green-400' : bid.status === 'rejected' ? 'bg-red-500/10 text-red-400' : 'bg-secondary text-muted-foreground'}`}>
                              {BID_NAME[bid.status] || bid.status}
                            </span>
                          </div>
                          <p className="text-sm mb-2">{bid.message || 'Без сообщения'}</p>
                          <p className="text-xs font-bold text-green-400">Предложение: {bid.price ? `${bid.price} ₸` : 'Договорная'}</p>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-sm text-muted-foreground bg-secondary/20 p-4 rounded-xl text-center">Пока нет откликов от мастеров.</p>}
                </div>
              </div>

              <div className="p-6 border-t border-border bg-secondary/10 flex justify-between gap-3 mt-auto">
                {canCancel ? (
                  <button onClick={cancelOrder} className="px-4 py-2 flex items-center gap-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 font-bold rounded-xl transition-all">
                    <Ban className="w-4 h-4" />Отменить заказ
                  </button>
                ) : <span />}
                <button onClick={() => setSelectedOrder(null)} className="px-6 py-2 bg-secondary hover:bg-secondary/80 font-bold rounded-xl transition-all">Закрыть</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
