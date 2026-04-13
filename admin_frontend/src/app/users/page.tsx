'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { 
  ArrowLeft, 
  Search, 
  User as UserIcon,
  Phone,
  MessageSquare,
  Activity,
  XCircle,
  Medal,
  CheckCircle,
  ShieldAlert,
  Briefcase
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Pagination from '@/components/Pagination';

export default function UsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 20;
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  
  // State for modal
  const [selectedUser, setSelectedUser] = useState<any | null>(null);
  const router = useRouter();

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const params = {
        skip: skip,
        limit: limit,
        role: roleFilter !== 'ALL' ? roleFilter : undefined
      };
      const response = await api.get('/users', { params });
      setUsers(response.data.items);
      setTotal(response.data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [skip, roleFilter]); // Refetch when page or role filter changes

  // Reset pagination when filter changes
  useEffect(() => {
    setSkip(0);
  }, [roleFilter]);

  const handleStatusUpdate = async (masterId: number, status: string) => {
    try {
      await api.patch(`/masters/${masterId}`, { status });
      // Update local state without fetching again to optimize UI if needed, but fetching is simpler
      fetchUsers();
      // Update selectedUser if open
      if (selectedUser && selectedUser.master_data && selectedUser.master_data.master_id === masterId) {
         setSelectedUser({...selectedUser, master_data: {...selectedUser.master_data, status}});
      }
    } catch (err) { alert('Ошибка обновления'); }
  };

  const toggleAccreditation = async (masterId: number, current: boolean) => {
    try {
      await api.patch(`/masters/${masterId}`, { is_accredited: !current });
      fetchUsers();
      if (selectedUser && selectedUser.master_data && selectedUser.master_data.master_id === masterId) {
         setSelectedUser({...selectedUser, master_data: {...selectedUser.master_data, is_accredited: !current}});
      }
    } catch (err) { alert('Ошибка'); }
  };

  const filteredUsers = users.filter(u => {
    const matchesSearch = 
      u.full_name?.toLowerCase().includes(filter.toLowerCase()) || 
      u.phone?.includes(filter) ||
      u.username?.toLowerCase().includes(filter.toLowerCase());
    const matchesRole = roleFilter === 'ALL' || u.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  return (
    <div className="min-h-screen bg-background p-6 lg:p-10">
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-3xl font-bold">Пользователи</h1>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-8">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input 
            type="text" 
            placeholder="Поиск по имени, логину или телефону..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full bg-secondary/50 border border-border rounded-xl py-2.5 pl-10 pr-4 focus:ring-2 focus:ring-primary outline-none"
          />
        </div>
        <div className="flex bg-secondary/50 p-1 rounded-xl border border-border">
          {['ALL', 'CLIENT', 'MASTER'].map((r) => (
            <button
              key={r}
              onClick={() => setRoleFilter(r)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                roleFilter === r ? 'bg-primary text-white shadow-lg' : 'hover:bg-background/50'
              }`}
            >
              {r === 'ALL' ? 'Все' : r === 'CLIENT' ? 'Клиенты' : 'Мастера'}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="glass-card rounded-2xl overflow-hidden border border-border">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-secondary/30 border-b border-border">
              <tr>
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Пользователь</th>
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Роль</th>
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Контакты</th>
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Инфо / Категория</th>
                <th className="px-6 py-4 text-sm font-semibold text-muted-foreground text-right">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <AnimatePresence>
                {filteredUsers.map((u) => (
                  <motion.tr 
                    key={u.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="hover:bg-secondary/20 transition-colors cursor-pointer"
                    onClick={() => setSelectedUser(u)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                          u.role === 'MASTER' ? 'bg-purple-500/10 text-purple-500' : 'bg-blue-500/10 text-blue-500'
                        }`}>
                          {u.full_name?.[0] || '?'}
                        </div>
                        <div>
                          <p className="font-bold">{u.full_name}</p>
                          <p className="text-xs text-muted-foreground">ID: {u.id}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${
                         u.role === 'MASTER' ? 'bg-purple-500/10 text-purple-500' : 'bg-blue-500/10 text-blue-500'
                      }`}>
                        {u.role === 'MASTER' ? 'Мастер' : 'Клиент'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium">
                        {u.phone ? <p>{u.phone}</p> : <p className="text-muted-foreground">-</p>}
                        {u.username && <p className="text-xs text-muted-foreground">@{u.username}</p>}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {u.role === 'MASTER' && u.master_data ? (
                        <div>
                           <p className="text-sm font-bold text-primary truncate max-w-[200px]">
                              {u.master_data.categories.join(', ') || 'Без категории'}
                           </p>
                           <p className="text-xs text-muted-foreground truncate max-w-[200px]" title={u.master_data.description}>
                              {u.master_data.description || '-'}
                           </p>
                        </div>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button 
                        onClick={(e) => { e.stopPropagation(); setSelectedUser(u); }}
                        className="px-3 py-1.5 bg-secondary hover:bg-secondary/80 text-sm font-medium rounded-lg transition-colors"
                      >
                        Статистика
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
          {filteredUsers.length === 0 && !loading && (
            <div className="p-10 text-center text-muted-foreground">
              Пользователи не найдены
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

      {/* Modal - User Details & Stats */}
      <AnimatePresence>
        {selectedUser && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-2xl bg-popover text-popover-foreground rounded-2xl shadow-2xl border border-border overflow-hidden"
            >
              <div className="p-6 border-b border-border flex items-center justify-between">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  {selectedUser.role === 'MASTER' ? <Briefcase className="text-purple-400" /> : <UserIcon className="text-blue-400" />}
                  Карточка пользователя
                </h2>
                <button onClick={() => setSelectedUser(null)} className="p-2 hover:bg-secondary rounded-full">
                  <XCircle className="w-6 h-6 text-muted-foreground" />
                </button>
              </div>

              <div className="p-6 space-y-6">
                {/* Contact section */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-secondary/30 p-4 rounded-xl">
                    <p className="text-sm text-muted-foreground mb-1">Имя</p>
                    <p className="font-bold text-lg">{selectedUser.full_name}</p>
                    {selectedUser.username && <p className="text-sm text-primary">@{selectedUser.username}</p>}
                  </div>
                  <div className="bg-secondary/30 p-4 rounded-xl">
                    <p className="text-sm text-muted-foreground mb-1">Телефон</p>
                    <p className="font-bold text-lg flex items-center gap-2">
                      <Phone className="w-4 h-4 text-green-400" />
                      {selectedUser.phone || 'Не указан'}
                    </p>
                  </div>
                </div>

                {/* Master Details if applicable */}
                {selectedUser.role === 'MASTER' && selectedUser.master_data && (
                  <div className="border border-border p-4 rounded-xl space-y-3">
                    <h3 className="font-bold text-lg border-b border-border pb-2">Профиль мастера</h3>
                    <div>
                      <p className="text-sm text-muted-foreground">Категории</p>
                      <p className="font-medium">{selectedUser.master_data.categories.join(', ') || 'Не указаны'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Описание ("Имя/опыт", которое он указал)</p>
                      <p className="font-medium bg-secondary/50 p-3 rounded-lg text-sm mt-1">
                        {selectedUser.master_data.description || 'Нет описания'}
                      </p>
                    </div>

                    <div className="pt-4 border-t border-border flex items-center justify-between">
                       <div className="flex items-center gap-2">
                         <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase transition-all ${
                            selectedUser.master_data.status === 'APPROVED' ? 'bg-green-500/10 text-green-500' : 
                            selectedUser.master_data.status === 'PENDING' ? 'bg-orange-500/10 text-orange-500 animate-pulse' : 
                            'bg-red-500/10 text-red-500'
                          }`}>
                            СТАТУС: {selectedUser.master_data.status}
                          </span>
                       </div>
                       <div className="flex gap-2">
                          {selectedUser.master_data.status === 'PENDING' && (
                            <button 
                              onClick={() => handleStatusUpdate(selectedUser.master_data.master_id, 'APPROVED')}
                              className="px-3 py-1.5 flex items-center gap-1 bg-green-500/10 hover:bg-green-500/20 text-green-500 text-sm font-bold rounded-lg transition-colors"
                            >
                              <CheckCircle className="w-4 h-4" />
                              Одобрить
                            </button>
                          )}
                          <button 
                            onClick={() => handleStatusUpdate(selectedUser.master_data.master_id, 'REJECTED')}
                            className="px-3 py-1.5 flex items-center gap-1 bg-red-500/10 hover:bg-red-500/20 text-red-500 text-sm font-bold rounded-lg transition-colors"
                          >
                            <ShieldAlert className="w-4 h-4" />
                            Бан
                          </button>
                          <button 
                            onClick={() => toggleAccreditation(selectedUser.master_data.master_id, selectedUser.master_data.is_accredited)}
                            className={`px-3 py-1.5 flex items-center gap-1 text-sm font-bold rounded-lg transition-colors ${
                              selectedUser.master_data.is_accredited ? 'bg-yellow-500/20 text-yellow-500' : 'bg-secondary text-muted-foreground hover:bg-secondary/80'
                            }`}
                          >
                            <Medal className="w-4 h-4" />
                            {selectedUser.master_data.is_accredited ? 'Аккредитован' : 'Выдать аккредитацию'}
                          </button>
                       </div>
                    </div>
                  </div>
                )}

                {/* Statistics */}
                <div>
                  <h3 className="font-bold text-lg mb-3 flex items-center gap-2">
                    <Activity className="w-5 h-5 text-primary" />
                    Статистика активности
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-primary/5 border border-primary/20 p-4 rounded-xl text-center">
                      <p className="text-sm text-muted-foreground mb-2">Создано заказов (как клиент)</p>
                      <p className="text-3xl font-black text-white">{selectedUser.client_orders_count}</p>
                    </div>
                    
                    {selectedUser.role === 'MASTER' && selectedUser.master_data ? (
                      <div className="bg-purple-500/5 border border-purple-500/20 p-4 rounded-xl text-center">
                         <p className="text-sm text-muted-foreground mb-2">Обработано заказов (принятые отклики)</p>
                         <p className="text-3xl font-black text-purple-400">
                           {selectedUser.master_data.processed_orders} <span className="text-lg text-muted-foreground font-normal">/ {selectedUser.master_data.total_bids} откликов</span>
                         </p>
                      </div>
                    ) : (
                      <div className="bg-secondary/30 border border-border p-4 rounded-xl flex items-center justify-center">
                         <p className="text-sm text-muted-foreground">Не является мастером</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="p-6 border-t border-border bg-secondary/10 flex justify-end">
                <button 
                  onClick={() => setSelectedUser(null)}
                  className="px-6 py-2 bg-primary hover:bg-primary/90 text-white font-bold rounded-xl transition-all"
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
