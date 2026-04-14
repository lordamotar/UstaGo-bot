'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { 
  ArrowLeft, 
  History,
  ShieldCheck,
  Search,
  Calendar,
  Info
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Pagination from '@/components/Pagination';

export default function LogsPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const router = useRouter();

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const res = await api.get('/logs', {
        params: { skip, limit }
      });
      setLogs(res.data.items);
      setTotal(res.data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [skip, limit]);

  const filteredLogs = logs.filter(l => 
    l.action.toLowerCase().includes(filter.toLowerCase()) ||
    l.details?.toLowerCase().includes(filter.toLowerCase())
  );

  const getActionColor = (action: string) => {
    if (action.includes('SETTINGS')) return 'bg-orange-500/10 text-orange-500';
    if (action.includes('POINTS')) return 'bg-green-500/10 text-green-500';
    if (action.includes('TOPUP_APPROVED')) return 'bg-blue-500/10 text-blue-500';
    if (action.includes('TOPUP_REJECTED')) return 'bg-red-500/10 text-red-500';
    return 'bg-secondary text-muted-foreground';
  };

  return (
    <div className="min-h-screen bg-background text-foreground p-6 lg:p-10">
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <History className="w-8 h-8 text-primary" />
          Логи действий администратора
        </h1>
      </div>

      <div className="flex flex-col md:flex-row gap-4 mb-8 items-center justify-between">
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input 
            type="text" 
            placeholder="Поиск по действию или деталям..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full bg-secondary/50 border border-border rounded-xl py-2.5 pl-10 pr-4 focus:ring-2 focus:ring-primary outline-none"
          />
        </div>
        
        <div className="flex items-center gap-2">
           <span className="text-[10px] font-bold text-muted-foreground uppercase">Показывать по:</span>
           <div className="flex bg-secondary/50 p-1 rounded-lg border border-border">
             {[10, 20, 50, 100].map((val) => (
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

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary"></div>
        </div>
      ) : (
        <div className="glass-card rounded-2xl overflow-hidden border border-border">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-secondary/30 border-b border-border">
                <tr>
                  <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Дата</th>
                  <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Действие</th>
                  <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Детали</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <AnimatePresence>
                  {filteredLogs.map((l) => (
                    <motion.tr 
                      key={l.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="hover:bg-secondary/20 transition-colors"
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2 text-sm">
                          <Calendar className="w-4 h-4 text-muted-foreground" />
                          {new Date(l.created_at).toLocaleString()}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 rounded-md text-[10px] font-bold uppercase ${getActionColor(l.action)}`}>
                          {l.action}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-start gap-2">
                           <Info className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                           <p className="text-sm text-balance">{l.details || '—'}</p>
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
            
            {filteredLogs.length === 0 && (
              <div className="p-20 text-center text-muted-foreground">
                Логов не найдено
              </div>
            )}
          </div>
          
          <div className="p-4 border-t border-border bg-secondary/10">
            <Pagination 
              total={total} 
              limit={limit} 
              skip={skip} 
              onPageChange={setSkip} 
            />
          </div>
        </div>
      )}
    </div>
  );
}
