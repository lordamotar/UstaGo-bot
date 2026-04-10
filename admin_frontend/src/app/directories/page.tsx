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

export default function DirectoriesPage() {
  const [categories, setCategories] = useState<any[]>([]);
  const [districts, setDistricts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'categories' | 'districts'>('categories');
  const [newItemName, setNewItemName] = useState('');
  const router = useRouter();

  const fetchData = async () => {
    try {
      setLoading(true);
      const [catRes, distRes] = await Promise.all([
        api.get('/categories'),
        api.get('/districts')
      ]);
      setCategories(catRes.data);
      setDistricts(distRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

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
        fetchData();
      } else {
        alert('Удаление районов пока не поддерживается API');
      }
    } catch (err) {
      alert('Ошибка при удалении');
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

      <div className="flex gap-4 mb-8 border-b border-border pb-4">
        <button 
          onClick={() => setActiveTab('categories')}
          className={`px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'categories' ? 'bg-primary text-white' : 'text-muted-foreground hover:bg-secondary/80'}`}
        >
          <Briefcase className="w-4 h-4" />
          Категории услуг
        </button>
        <button 
          onClick={() => setActiveTab('districts')}
          className={`px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'districts' ? 'bg-primary text-white' : 'text-muted-foreground hover:bg-secondary/80'}`}
        >
          <MapPin className="w-4 h-4" />
          Районы города
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-1">
          <div className="glass-card p-6 rounded-2xl border border-border">
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
            <div className="glass-card rounded-2xl overflow-hidden border border-border">
               <ul className="divide-y divide-border">
                  <AnimatePresence>
                    {(activeTab === 'categories' ? categories : districts).map((item) => (
                      <motion.li 
                        key={item.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="p-4 flex items-center justify-between hover:bg-secondary/20 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-secondary rounded-lg">
                            {activeTab === 'categories' ? <Briefcase className="w-4 h-4 text-primary" /> : <MapPin className="w-4 h-4 text-green-400" />}
                          </div>
                          <span className="font-medium text-lg">{item.name}</span>
                        </div>
                        {activeTab === 'categories' && (
                          <button 
                            onClick={() => handleDelete(item.id)}
                            className="p-2 text-muted-foreground hover:bg-red-500/10 hover:text-red-500 rounded-lg transition-colors"
                          >
                            <Trash2 className="w-5 h-5" />
                          </button>
                        )}
                      </motion.li>
                    ))}
                  </AnimatePresence>
               </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
