'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { 
  ArrowLeft, 
  CreditCard,
  History,
  CheckCircle,
  XCircle,
  Check,
  X,
  Settings,
  Zap,
  ZapOff,
  Search
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Pagination from '@/components/Pagination';

export default function FinancesPage() {
  const [topups, setTopups] = useState<any[]>([]);
  const [topupTotal, setTopupTotal] = useState(0);
  const [topupSkip, setTopupSkip] = useState(0);
  const [topupLimit, setTopupLimit] = useState(10);

  const [transactions, setTransactions] = useState<any[]>([]);
  const [txTotal, setTxTotal] = useState(0);
  const [txSkip, setTxSkip] = useState(0);
  const [txLimit, setTxLimit] = useState(20);

  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'topups' | 'transactions'>('topups');
  
  // Modal state
  const [isAddPointsModalOpen, setIsAddPointsModalOpen] = useState(false);
  const [masters, setMasters] = useState<any[]>([]);
  const [searchMaster, setSearchMaster] = useState('');
  const [selectedMasterIds, setSelectedMasterIds] = useState<number[]>([]);
  const [allMasters, setAllMasters] = useState(false);
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('Бонус от администрации');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const router = useRouter();

  const fetchMasters = async () => {
    try {
      const res = await api.get('/users', { params: { role: 'MASTER', limit: 100 } });
      setMasters(res.data.items);
    } catch (err) { console.error(err); }
  };

  const fetchTransactions = async () => {
    try {
      const txsRes = await api.get(`/transactions?skip=${txSkip}&limit=${txLimit}`);
      setTransactions(txsRes.data.items);
      setTxTotal(txsRes.data.total);
    } catch (err) { console.error(err); }
  };

  const fetchTopups = async () => {
    try {
      const res = await api.get('/topups', {
        params: { skip: topupSkip, limit: topupLimit, status: 'PENDING' }
      });
      setTopups(res.data.items);
      setTopupTotal(res.data.total);
    } catch (err) { console.error(err); }
  }

  const fetchData = async () => {
    try {
      setLoading(true);
      const settingsRes = await api.get('/settings');
      setSettings(settingsRes.data);
      await Promise.all([fetchTopups(), fetchTransactions(), fetchMasters()]);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (activeTab === 'transactions') {
      fetchTransactions();
    } else {
      fetchTopups();
    }
  }, [txSkip, txLimit, topupSkip, topupLimit, activeTab]);

  const handleTopupReview = async (id: number, status: string) => {
    try {
      await api.patch(`/topups/${id}`, { status });
      fetchData();
    } catch (err) {
      alert('Ошибка при обновлении статуса');
    }
  };

  const toggleFreeOrders = async () => {
    if (!settings) return;
    try {
      const newValue = !settings.free_orders_enabled;
      await api.patch('/settings', { free_orders_enabled: newValue });
      setSettings({ ...settings, free_orders_enabled: newValue });
    } catch (err) {
      alert('Ошибка при обновлении настроек');
    }
  };

  const handleAddPoints = async () => {
    if (!amount || (!allMasters && selectedMasterIds.length === 0)) {
      alert('Заполните все поля');
      return;
    }

    try {
      setIsSubmitting(true);
      await api.post('/finance/bulk-adjust-points', {
        master_ids: allMasters ? null : selectedMasterIds,
        all_masters: allMasters,
        amount: parseInt(amount),
        description: reason
      });
      alert('Баллы успешно начислены');
      setIsAddPointsModalOpen(false);
      resetModal();
      fetchData();
    } catch (err) {
      alert('Ошибка при начислении');
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetModal = () => {
    setSelectedMasterIds([]);
    setAllMasters(false);
    setAmount('');
    setReason('Бонус от администрации');
    setSearchMaster('');
  };

  const filteredMasters = masters.filter(m => 
    m.full_name?.toLowerCase().includes(searchMaster.toLowerCase()) ||
    m.phone?.includes(searchMaster)
  );

  return (
    <div className="min-h-screen bg-background p-6 lg:p-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8">
        <div className="flex items-center gap-4">
          <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-3xl font-bold">Управление финансами</h1>
        </div>

        {settings && (
          <div className="bg-secondary/50 p-1.5 rounded-2xl flex items-center border border-border">
            <div className="flex items-center gap-3 px-4 py-2 bg-background/50 rounded-xl border border-border/50 shadow-sm">
              <div className={`p-2 rounded-lg ${settings.free_orders_enabled ? 'bg-green-500/20 text-green-500' : 'bg-primary/20 text-primary'}`}>
                {settings.free_orders_enabled ? <Zap className="w-5 h-5" /> : <ZapOff className="w-5 h-5" />}
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Платные заказы</span>
                <span className="text-sm font-bold">
                  {settings.free_orders_enabled ? 'Баллы НЕ списываются' : 'Баллы списываются (50 баллов)'}
                </span>
              </div>
              <button 
                onClick={toggleFreeOrders}
                className={`ml-4 w-12 h-6 rounded-full p-1 transition-colors duration-300 relative ${settings.free_orders_enabled ? 'bg-green-500' : 'bg-muted'}`}
              >
                <div className={`w-4 h-4 bg-white rounded-full transition-transform duration-300 ${settings.free_orders_enabled ? 'translate-x-6' : 'translate-x-0'}`} />
              </button>
            </div>
          </div>
        )}
      </div>


      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div className="flex gap-4">
          <button 
            onClick={() => setActiveTab('topups')}
            className={`px-6 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'topups' ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'bg-secondary text-muted-foreground hover:bg-secondary/80'}`}
          >
            <CreditCard className="w-4 h-4" />
            Заявки на пополнение
            {totalTopups > 0 && (
              <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full ml-1">
                {totalTopups}
              </span>
            )}
          </button>
          <button 
            onClick={() => setActiveTab('transactions')}
            className={`px-6 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'transactions' ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'bg-secondary text-muted-foreground hover:bg-secondary/80'}`}
          >
            <History className="w-4 h-4" />
            Сводка транзакций
          </button>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-muted-foreground uppercase">Показывать по:</span>
            <div className="flex bg-secondary/50 p-1 rounded-xl border border-border">
              {[10, 20, 50, 100].map((val) => (
                <button
                  key={val}
                  onClick={() => { 
                    if (activeTab === 'topups') { setTopupLimit(val); setTopupSkip(0); }
                    else { setTxLimit(val); setTxSkip(0); }
                  }}
                  className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${(activeTab === 'topups' ? topupLimit : txLimit) === val ? 'bg-primary text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  {val}
                </button>
              ))}
            </div>
          </div>
          <button 
            onClick={() => { resetModal(); fetchMasters(); setIsAddPointsModalOpen(true); }}
            className="px-6 py-2 bg-green-500 hover:bg-green-600 text-white rounded-xl text-sm font-bold flex items-center gap-2 shadow-lg shadow-green-500/20 transition-all font-outfit"
          >
            <CreditCard className="w-4 h-4" />
            Добавить баллы
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary"></div>
        </div>
      ) : (
        <div className="glass-card rounded-2xl overflow-hidden border border-border">
          <div className="overflow-x-auto">
            {activeTab === 'topups' ? (
              <table className="w-full text-left">
                <thead className="bg-secondary/30 border-b border-border">
                  <tr>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">ID/Дата</th>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Пользователь</th>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Сумма / Способ</th>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Данные о платеже</th>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground text-right">Действия</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  <AnimatePresence>
                    {topups.map((t) => (
                      <motion.tr 
                        key={t.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="hover:bg-secondary/20 transition-colors"
                      >
                        <td className="px-6 py-4">
                          <p className="font-bold">#{t.id}</p>
                          <p className="text-xs text-muted-foreground">{new Date(t.created_at).toLocaleString()}</p>
                        </td>
                        <td className="px-6 py-4 font-medium">{t.user_name}</td>
                        <td className="px-6 py-4">
                          <p className="font-bold text-green-400">+{t.amount} ₸</p>
                          <p className="text-xs text-muted-foreground">{t.method}</p>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm font-mono bg-secondary/50 px-2 py-1 rounded">
                            {t.receipt || 'Нет данных'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-end gap-2">
                            <button 
                              onClick={() => handleTopupReview(t.id, 'APPROVED')}
                              className="p-2 bg-green-500/10 text-green-500 hover:bg-green-500/20 rounded-lg transition-colors flex items-center justify-center"
                              title="Одобрить"
                            >
                              <Check className="w-5 h-5" />
                            </button>
                            <button 
                              onClick={() => handleTopupReview(t.id, 'REJECTED')}
                              className="p-2 bg-red-500/10 text-red-500 hover:bg-red-500/20 rounded-lg transition-colors flex items-center justify-center"
                              title="Отклонить"
                            >
                              <X className="w-5 h-5" />
                            </button>
                          </div>
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            ) : (
              <table className="w-full text-left">
                <thead className="bg-secondary/30 border-b border-border">
                  <tr>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">ID/Дата</th>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Пользователь</th>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Тип</th>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Изменение</th>
                    <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Описание</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {transactions.map((tx) => (
                    <tr key={tx.id} className="hover:bg-secondary/20 transition-colors">
                      <td className="px-6 py-4">
                        <p className="font-bold">#{tx.id}</p>
                        <p className="text-xs text-muted-foreground">{new Date(tx.date).toLocaleString()}</p>
                      </td>
                      <td className="px-6 py-4 font-medium">{tx.user}</td>
                      <td className="px-6 py-4">
                        <span className="text-xs font-bold px-2 py-1 rounded-full bg-secondary">
                          {tx.type}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono font-bold">
                        {tx.amount > 0 ? (
                          <span className="text-green-400">+{tx.amount} ₸</span>
                        ) : (
                          <span className="text-red-400">{tx.amount} ₸</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {tx.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            
            {(activeTab === 'topups' && topups.length === 0) && (
              <div className="p-10 text-center text-muted-foreground">
                Нет новых заявок на пополнение в данный момент.
              </div>
            )}
            
            {(activeTab === 'transactions' && transactions.length === 0) && (
              <div className="p-10 text-center text-muted-foreground">
                Транзакции отсутствуют.
              </div>
            )}
          </div>
          
          <div className="p-4 border-t border-border bg-secondary/10">
            {activeTab === 'topups' ? (
              <Pagination 
                total={topupTotal} 
                limit={topupLimit} 
                skip={topupSkip} 
                onPageChange={setTopupSkip} 
              />
            ) : (
              <Pagination 
                total={txTotal} 
                limit={txLimit} 
                skip={txSkip} 
                onPageChange={setTxSkip} 
              />
            )}
          </div>
        </div>
      )}

      {/* Add Points Modal */}
      <AnimatePresence>
        {isAddPointsModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-lg bg-popover text-popover-foreground rounded-2xl shadow-2xl border border-border overflow-hidden"
            >
              <div className="p-6 border-b border-border flex items-center justify-between">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <CreditCard className="text-green-500" />
                  Начислить баллы
                </h2>
                <button onClick={() => setIsAddPointsModalOpen(false)} className="p-2 hover:bg-secondary rounded-full">
                  <X className="w-5 h-5 text-muted-foreground" />
                </button>
              </div>

              <div className="p-6 space-y-4">
                <div className="flex items-center gap-2 mb-2">
                   <input 
                     type="checkbox" 
                     id="all_masters" 
                     checked={allMasters} 
                     onChange={(e) => setAllMasters(e.target.checked)}
                     className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
                   />
                   <label htmlFor="all_masters" className="text-sm font-bold cursor-pointer">
                      Пополнить ВСЕМ мастерам
                   </label>
                </div>

                {!allMasters && (
                  <div>
                    <label className="text-xs font-bold text-muted-foreground uppercase mb-1 block">Выберите мастера</label>
                    <div className="relative mb-2">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <input 
                        type="text" 
                        placeholder="Поиск мастера..." 
                        value={searchMaster}
                        onChange={(e) => setSearchMaster(e.target.value)}
                        className="w-full bg-secondary/50 border border-border rounded-xl py-2 pl-9 pr-4 text-sm outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div className="max-h-[150px] overflow-y-auto border border-border rounded-xl bg-secondary/20 p-1 space-y-1">
                      {filteredMasters.map(m => (
                        <div 
                          key={m.id} 
                          onClick={() => {
                            if (selectedMasterIds.includes(m.master_data.master_id)) {
                              setSelectedMasterIds(selectedMasterIds.filter(id => id !== m.master_data.master_id));
                            } else {
                              setSelectedMasterIds([...selectedMasterIds, m.master_data.master_id]);
                            }
                          }}
                          className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors ${
                            selectedMasterIds.includes(m.master_data.master_id) ? 'bg-primary/20 text-primary' : 'hover:bg-secondary'
                          }`}
                        >
                          <div className="text-xs">
                             <p className="font-bold">{m.full_name}</p>
                             <p className="text-muted-foreground">{m.phone}</p>
                          </div>
                          {selectedMasterIds.includes(m.master_data.master_id) && <Check className="w-4 h-4" />}
                        </div>
                      ))}
                      {filteredMasters.length === 0 && <p className="p-4 text-center text-xs text-muted-foreground">Мастера не найдены</p>}
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-1">Выбрано: {selectedMasterIds.length}</p>
                  </div>
                )}

                <div>
                   <label className="text-xs font-bold text-muted-foreground uppercase mb-1 block">Сумма баллов</label>
                   <input 
                     type="number" 
                     placeholder="Например: 500" 
                     value={amount}
                     onChange={(e) => setAmount(e.target.value)}
                     className="w-full bg-secondary/50 border border-border rounded-xl py-2.5 px-4 text-sm font-bold outline-none focus:ring-2 focus:ring-primary"
                   />
                </div>

                <div>
                   <label className="text-xs font-bold text-muted-foreground uppercase mb-1 block">Комментарий</label>
                   <input 
                     type="text" 
                     value={reason}
                     onChange={(e) => setReason(e.target.value)}
                     className="w-full bg-secondary/50 border border-border rounded-xl py-2.5 px-4 text-sm outline-none focus:ring-2 focus:ring-primary"
                   />
                </div>
              </div>

              <div className="p-6 bg-secondary/10 border-t border-border flex justify-end gap-3">
                <button 
                  onClick={() => setIsAddPointsModalOpen(false)}
                  className="px-6 py-2 bg-secondary hover:bg-secondary/80 font-bold rounded-xl transition-all"
                >
                  Отмена
                </button>
                <button 
                  onClick={handleAddPoints}
                  disabled={isSubmitting}
                  className="px-6 py-2 bg-green-500 hover:bg-green-600 disabled:opacity-50 text-white font-bold rounded-xl transition-all shadow-lg shadow-green-500/20"
                >
                  {isSubmitting ? 'Выполняется...' : 'Начислить'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
