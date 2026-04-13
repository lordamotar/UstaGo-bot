'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { 
  ArrowLeft, 
  Search, 
  ShoppingBag,
  MapPin,
  Calendar,
  DollarSign,
  AlertCircle
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Pagination from '@/components/Pagination';

export default function OrdersPage() {
  const [orders, setOrders] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 20;
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedOrder, setSelectedOrder] = useState<any | null>(null);
  
  const router = useRouter();

  const fetchOrders = async () => {
    try {
      setLoading(true);
      const params = {
        skip: skip,
        limit: limit,
        status: statusFilter !== 'ALL' ? statusFilter : undefined
      };
      const response = await api.get('/orders', { params });
      setOrders(response.data.items);
      setTotal(response.data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [skip, statusFilter]);

  // Reset pagination when filter changes
  useEffect(() => {
    setSkip(0);
  }, [statusFilter]);

  const fetchOrderDetails = async (id: number) => {
    try {
      const res = await api.get(`/orders/${id}`);
      setSelectedOrder(res.data);
    } catch (err) {
      alert('Ошибка при загрузке заявки');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'NEW': return 'bg-blue-500/10 text-blue-500';
      case 'ACTIVE': return 'bg-yellow-500/10 text-yellow-500';
      case 'COMPLETED': return 'bg-green-500/10 text-green-500';
      case 'CANCELLED': return 'bg-red-500/10 text-red-500';
      default: return 'bg-secondary text-muted-foreground';
    }
  };

  const getStatusName = (status: string) => {
    switch (status) {
      case 'NEW': return 'Новый';
      case 'ACTIVE': return 'В работе';
      case 'COMPLETED': return 'Завершен';
      case 'CANCELLED': return 'Отменен';
      default: return status;
    }
  };

  const filteredOrders = orders.filter(o => {
    const matchesSearch = 
      o.category?.toLowerCase().includes(filter.toLowerCase()) || 
      o.district?.toLowerCase().includes(filter.toLowerCase()) ||
      o.id.toString().includes(filter);
    const matchesStatus = statusFilter === 'ALL' || o.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="min-h-screen bg-background p-6 lg:p-10">
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-3xl font-bold">Управление заказами</h1>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-8">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input 
            type="text" 
            placeholder="Поиск по категории, району или ID..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full bg-secondary/50 border border-border rounded-xl py-2.5 pl-10 pr-4 focus:ring-2 focus:ring-primary outline-none"
          />
        </div>
        <div className="flex bg-secondary/50 p-1 rounded-xl border border-border overflow-x-auto">
          {['ALL', 'NEW', 'ACTIVE', 'COMPLETED', 'CANCELLED'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                statusFilter === s ? 'bg-primary text-white shadow-lg' : 'hover:bg-background/50'
              }`}
            >
              {s === 'ALL' ? 'Все' : getStatusName(s)}
            </button>
          ))}
        </div>
      </div>

      {/* Orders Table */}
      <div className="glass-card rounded-2xl overflow-hidden border border-border">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-secondary/30 border-b border-border">
              <tr>
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">ID / Дата</th>
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Статус</th>
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Категория / Район</th>
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground text-right">Детали</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <AnimatePresence>
                {filteredOrders.map((o) => (
                  <motion.tr 
                    key={o.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="hover:bg-secondary/20 transition-colors cursor-pointer"
                    onClick={() => fetchOrderDetails(o.id)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-bold"># {o.id}</span>
                        <span className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                          <Calendar className="w-3 h-3" />
                          {new Date(o.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${getStatusColor(o.status)}`}>
                        {getStatusName(o.status)}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                       <div className="flex flex-col">
                         <span className="font-bold">{o.category}</span>
                         <span className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                           <MapPin className="w-3 h-3" />
                           {o.district || 'Весь город'}
                         </span>
                       </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button 
                        className="px-3 py-1.5 bg-secondary hover:bg-secondary/80 text-sm font-medium rounded-lg transition-colors"
                      >
                        Подробнее
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
          {filteredOrders.length === 0 && !loading && (
            <div className="p-10 text-center text-muted-foreground">
              Заказы не найдены
            </div>
          )}
          {loading && (
            <div className="p-10 flex justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary"></div>
            </div>
          )}
        </div>
        <Pagination 
          total={total} 
          limit={limit} 
          skip={skip} 
          onPageChange={setSkip} 
        />
      </div>

      {/* Modal - Order Details */}
      <AnimatePresence>
        {selectedOrder && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-2xl bg-popover text-popover-foreground rounded-2xl shadow-2xl border border-border overflow-hidden max-h-[90vh] flex flex-col"
            >
              <div className="p-6 border-b border-border flex items-center justify-between">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  <ShoppingBag className="text-orange-400" />
                  Заказ #{selectedOrder.id}
                </h2>
                <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${getStatusColor(selectedOrder.status)}`}>
                  {getStatusName(selectedOrder.status)}
                </span>
              </div>

              <div className="p-6 overflow-y-auto space-y-6">
                
                {/* Description */}
                <div>
                   <h3 className="text-sm font-bold text-muted-foreground mb-2">Описание задачи</h3>
                   <div className="bg-secondary/30 p-4 rounded-xl border border-border">
                      <p className="whitespace-pre-wrap">{selectedOrder.description}</p>
                   </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-secondary/30 p-4 rounded-xl border border-border">
                    <p className="text-sm text-muted-foreground mb-1">Клиент</p>
                    <p className="font-bold">{selectedOrder.client.name}</p>
                    <p className="text-xs text-primary mt-1">{selectedOrder.client.phone}</p>
                  </div>
                  <div className="bg-secondary/30 p-4 rounded-xl border border-border">
                    <p className="text-sm text-muted-foreground mb-1">Ориентир бюджета</p>
                    <p className="font-bold flex items-center gap-2">
                      <DollarSign className="w-4 h-4 text-green-400" />
                      {selectedOrder.budget ? `${selectedOrder.budget} ₸` : 'Не указан'}
                    </p>
                  </div>
                </div>

                {/* Bids */}
                <div>
                   <h3 className="text-sm font-bold text-muted-foreground mb-3 flex items-center gap-2">
                     <AlertCircle className="w-4 h-4" />
                     Отклики мастеров ({selectedOrder.bids.length})
                   </h3>
                   {selectedOrder.bids.length > 0 ? (
                     <div className="space-y-3">
                       {selectedOrder.bids.map((bid: any) => (
                         <div key={bid.id} className="p-4 bg-secondary/20 border border-border rounded-xl">
                            <div className="flex items-center justify-between mb-2">
                               <p className="font-bold text-primary">{bid.master_name}</p>
                               <span className={`text-xs font-bold px-2 py-0.5 rounded-md ${
                                 bid.status === 'ACCEPTED' ? 'bg-green-500/20 text-green-400' : 'bg-secondary text-muted-foreground'
                               }`}>
                                 {bid.status}
                               </span>
                            </div>
                            <p className="text-sm mb-2">{bid.message || 'Без сообщения'}</p>
                            <p className="text-xs font-bold text-green-400">Предложение: {bid.price ? `${bid.price} ₸` : 'Договорная'}</p>
                         </div>
                       ))}
                     </div>
                   ) : (
                     <p className="text-sm text-muted-foreground bg-secondary/20 p-4 rounded-xl text-center">
                       Пока нет откликов от мастеров.
                     </p>
                   )}
                </div>

              </div>

              <div className="p-6 border-t border-border bg-secondary/10 flex justify-end gap-3 mt-auto">
                <button 
                  onClick={() => setSelectedOrder(null)}
                  className="px-6 py-2 bg-secondary hover:bg-secondary/80 font-bold rounded-xl transition-all"
                >
                  Закрыть
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
