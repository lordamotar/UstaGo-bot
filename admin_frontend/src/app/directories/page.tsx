'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { 
  ArrowLeft, 
  MapPin,
  Briefcase,
  Plus,
  Trash2
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Pagination from '@/components/Pagination';

export default function DirectoriesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(10); // Default to 10
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'categories' | 'districts'>('categories');
  const [newItemName, setNewItemName] = useState('');
  const router = useRouter();

  const fetchData = async () => {
    try {
      setLoading(true);
      const url = activeTab === 'categories' ? '/categories' : '/districts';
      const response = await api.get(url, {
        params: { skip, limit }
      });
      setItems(response.data.items);
      setTotal(response.data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [skip, limit, activeTab]);

  useEffect(() => {
    setSkip(0);
  }, [activeTab]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newItemName.trim()) return;

    try {
      if (activeTab === 'categories') {
        await api.post('/categories', { name: newItemName });
      } else {
        await api.post('/districts', { name: newItemName });
      }
      setNewItemName('');
      setSkip(0); // Reset to first page
      fetchData();
    } catch (err) {
      alert('Ошибка при добавлении');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить эту запись?')) return;
    try {
      if (activeTab === 'categories') {
        await api.delete(`/categories/${id}`);
      } else {
        await api.delete(`/districts/${id}`);
      }
      fetchData();
    } catch (err) {
      alert('Ошибка при удалении. Вероятно, эта запись используется в заказах или профилях мастеров.');
    }
  };

  return (
    <div className="min-h-screen bg-background p-6 lg:p-10">
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-3xl font-bold">Справочники системы</h1>
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 border-b border-border pb-4">
        <div className="flex gap-4">
          <button 
            onClick={() => setActiveTab('categories')}
            className={`px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'categories' ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'text-muted-foreground hover:bg-secondary/80'}`}
          >
            <Briefcase className="w-4 h-4" />
            Категории услуг
          </button>
          <button 
            onClick={() => setActiveTab('districts')}
            className={`px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'districts' ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'text-muted-foreground hover:bg-secondary/80'}`}
          >
            <MapPin className="w-4 h-4" />
            Районы города
          </button>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-bold text-muted-foreground uppercase">Показывать по:</span>
          <div className="flex bg-secondary/50 p-1 rounded-lg border border-border">
            {[10, 50, 100].map((val) => (
              <button
                key={val}
                onClick={() => { setLimit(val); setSkip(0); }}
                className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${limit === val ? 'bg-primary text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
              >
                {val}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-1">
          <div className="glass-card p-6 rounded-2xl border border-border sticky top-10">
            <h3 className="text-lg font-bold mb-4">
              Добавить {activeTab === 'categories' ? 'категорию' : 'район'}
            </h3>
            <form onSubmit={handleAdd} className="flex flex-col gap-4">
              <input 
                type="text" 
                placeholder="Название..."
                value={newItemName}
                onChange={(e) => setNewItemName(e.target.value)}
                className="w-full bg-secondary/50 border border-border rounded-xl py-2 px-4 focus:ring-2 focus:ring-primary outline-none"
              />
              <button 
                type="submit" 
                className="flex items-center justify-center gap-2 w-full py-2 bg-primary hover:bg-primary/90 text-white rounded-xl font-medium transition-all"
              >
                <Plus className="w-4 h-4" />
                Сохранить
              </button>
            </form>
          </div>
        </div>

        <div className="md:col-span-2">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary"></div>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="glass-card rounded-2xl overflow-hidden border border-border">
                 <ul className="divide-y divide-border">
                    <AnimatePresence mode="popLayout">
                      {items.map((item) => (
                        <motion.li 
                          key={item.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 10 }}
                          transition={{ duration: 0.2 }}
                          className="p-4 flex items-center justify-between hover:bg-secondary/20 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <div className="p-2 bg-secondary rounded-lg">
                              {activeTab === 'categories' ? <Briefcase className="w-4 h-4 text-primary" /> : <MapPin className="w-4 h-4 text-green-400" />}
                            </div>
                            <span className="font-medium text-lg">{item.name}</span>
                          </div>
                          <button 
                            onClick={() => handleDelete(item.id)}
                            className="p-2 text-muted-foreground hover:bg-red-500/10 hover:text-red-500 rounded-lg transition-colors"
                          >
                            <Trash2 className="w-5 h-5" />
                          </button>
                        </motion.li>
                      ))}
                    </AnimatePresence>
                 </ul>
                 {items.length === 0 && (
                   <div className="p-10 text-center text-muted-foreground italic">
                     Список пуст
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
          )}
        </div>
      </div>
    </div>
  );
}
