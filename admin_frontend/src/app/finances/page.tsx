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
  ZapOff
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function FinancesPage() {
  const [topups, setTopups] = useState<any[]>([]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'topups' | 'transactions'>('topups');
  const router = useRouter();

  const fetchData = async () => {
    try {
      setLoading(true);
      const [topupsRes, txsRes, settingsRes] = await Promise.all([
        api.get('/topups'),
        api.get('/transactions?limit=20'),
        api.get('/settings')
      ]);
      setTopups(topupsRes.data);
      setTransactions(txsRes.data);
      setSettings(settingsRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

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


      <div className="flex gap-4 mb-8">
        <button 
          onClick={() => setActiveTab('topups')}
          className={`px-6 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'topups' ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'bg-secondary text-muted-foreground hover:bg-secondary/80'}`}
        >
          <CreditCard className="w-4 h-4" />
          Заявки на пополнение
          {topups.length > 0 && (
            <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full ml-1">
              {topups.length}
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
        </div>
      )}
    </div>
  );
}
