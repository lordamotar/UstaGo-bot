'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { 
  Users, 
  Wrench, 
  ShoppingBag, 
  TrendingUp, 
  Hourglass,
  LogOut,
  BarChart3,
  CheckCircle2,
  CreditCard,
  MapPin,
  Settings,
  History,
  Database
} from 'lucide-react';
import ChangePasswordModal from '@/components/ChangePasswordModal';
import { 
  BarChart, 
  Bar, 
  LineChart,
  Line,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { motion } from 'framer-motion';

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [orderChartData, setOrderChartData] = useState<any[]>([]);
  const [chartRange, setChartRange] = useState<string>('7');
  const [viewMode, setViewMode] = useState<string>('total'); // 'total', 'category', 'district', 'master'
  const [customDates, setCustomDates] = useState({ start: '', end: '' });
  
  // New Filters
  const [categories, setCategories] = useState<any[]>([]);
  const [districts, setDistricts] = useState<any[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedDistrict, setSelectedDistrict] = useState<string>('');
  const [selectedMasterId, setSelectedMasterId] = useState<string>('');
  const [masters, setMasters] = useState<any[]>([]);

  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const router = useRouter();

  const fetchChartData = async (range: string, view: string, custom?: { start: string, end: string }) => {
    try {
      setChartLoading(true);
      let params: any = { 
        days: range !== 'custom' ? parseInt(range) : undefined,
        category_id: selectedCategory || undefined,
        district_id: selectedDistrict || undefined,
        master_id: selectedMasterId || undefined,
        split_by: view !== 'total' ? view : undefined
      };
      
      if (range === 'custom' && custom?.start && custom?.end) {
        params.start = custom.start;
        params.end = custom.end;
      }
      
      const response = await api.get('/stats/orders-chart', { params });
      setOrderChartData(response.data);
    } catch (err) {
      console.error(err);
    } finally {
      setChartLoading(false);
    }
  };

  useEffect(() => {
    const key = localStorage.getItem('admin_token');
    if (!key) {
      router.push('/login');
      return;
    }

    const fetchData = async () => {
      try {
        const [statsRes, catsRes, distsRes, mastersRes] = await Promise.all([
          api.get('/stats'),
          api.get('/categories'),
          api.get('/districts'),
          api.get('/masters')
        ]);
        
        setStats(statsRes.data);
        setCategories(catsRes.data.items);
        setDistricts(distsRes.data.items);
        setMasters(mastersRes.data);
        
        await fetchChartData(chartRange, viewMode);
      } catch (err) {
        console.error(err);
        localStorage.removeItem('admin_token');
        router.push('/login');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [router]);

  useEffect(() => {
     if (chartRange !== 'custom') {
       fetchChartData(chartRange, viewMode);
     }
  }, [chartRange, viewMode, selectedCategory, selectedDistrict, selectedMasterId]);

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    router.push('/login');
  };

  if (loading || !stats) return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-primary"></div>
        <p className="text-muted-foreground animate-pulse">Загрузка данных...</p>
      </div>
    </div>
  );

  const chartData = [
    { name: 'Клиенты', value: stats?.users?.clients || 0 },
    { name: 'Мастера', value: stats?.users?.masters || 0 },
  ];

  const COLORS = ['#6366f1', '#c084fc'];

  const getLineColor = (index: number) => {
    const colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6', '#06b6d4', '#f97316', '#14b8a6', '#3b82f6'];
    return colors[index % colors.length];
  };

  const seriesNames = orderChartData.length > 0 
    ? Object.keys(orderChartData[0]).filter(k => k !== 'date' && k !== 'full_date')
    : [];

  return (
    <div className="min-h-screen bg-background text-foreground p-6 lg:p-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-10">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight">Панель управления</h1>
          <p className="text-muted-foreground mt-1">Добро пожаловать в центр управления UstaGo</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-4 md:mt-0 self-start">
          <button 
            onClick={() => router.push('/users')}
            className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-xl transition-all shadow-lg shadow-primary/20"
          >
            <Users className="w-4 h-4" />
            Пользователи
          </button>
          <button 
            onClick={() => router.push('/orders')}
            className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-xl transition-all shadow-lg shadow-primary/20"
          >
            <ShoppingBag className="w-4 h-4" />
            Заказы
          </button>
          <button 
            onClick={() => router.push('/finances')}
            className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-xl transition-all shadow-lg shadow-primary/20"
          >
            <CreditCard className="w-4 h-4" />
            Финансы
          </button>
          <button 
            onClick={() => router.push('/directories')}
            className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-xl transition-all shadow-lg shadow-primary/20"
          >
            <MapPin className="w-4 h-4" />
            Справочники
          </button>
          <button 
            onClick={() => router.push('/logs')}
            className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-xl transition-all shadow-lg shadow-primary/20"
          >
            <History className="w-4 h-4" />
            Логи
          </button>
          <button 
            onClick={() => router.push('/backups')}
            className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-xl transition-all shadow-lg shadow-primary/20"
          >
            <Database className="w-4 h-4" />
            Бэкапы
          </button>
          <button 
            onClick={() => setIsPasswordModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 rounded-xl transition-colors"
          >
            <Settings className="w-4 h-4" />
            Пароль
          </button>
          <button 
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 rounded-xl transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Выйти
          </button>
        </div>
      </div>

      <ChangePasswordModal 
        isOpen={isPasswordModalOpen} 
        onClose={() => setIsPasswordModalOpen(false)} 
      />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        <StatCard 
          icon={<Users className="text-blue-400" />} 
          title="Пользователей" 
          value={stats.users.total} 
          subtitle="Всего в базе"
        />
        <StatCard 
          icon={<Wrench className="text-purple-400" />} 
          title="Мастеров" 
          value={stats.users.masters} 
          subtitle={`${stats.moderation.pending_masters} ожидают проверки`}
          highlight={stats.moderation.pending_masters > 0}
        />
        <StatCard 
          icon={<ShoppingBag className="text-orange-400" />} 
          title="Заказов" 
          value={stats.orders.active + stats.orders.new + stats.orders.completed} 
          subtitle={`${stats.orders.completed} завершено`}
        />
        <StatCard 
          icon={<CreditCard className="text-green-400" />} 
          title="Оборот (баллы)" 
          value={stats.finance.total_revenue} 
          subtitle={`Всего пополнений: ${stats.finance.total_deposits}`}
        />
      </div>

      {/* Order Dynamics Chart */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-6 rounded-2xl mb-10 overflow-hidden"
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h2 className="text-xl font-bold flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              Динамика поступления заказов
            </h2>
            <p className="text-sm text-muted-foreground mt-1">Количество новых заказов по дням</p>
          </div>
          
          <div className="flex flex-col items-end gap-3">
            <div className="flex flex-wrap items-center gap-2 bg-secondary/50 p-1 rounded-xl border border-border">
              {[
                { label: '7д', value: '7' },
                { label: '14д', value: '14' },
                { label: '30д', value: '30' },
                { label: '90д', value: '90' },
                { label: 'Год', value: '365' },
                { label: 'Свой', value: 'custom' }
              ].map((r) => (
                <button
                  key={r.value}
                  onClick={() => setChartRange(r.value)}
                  className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                    chartRange === r.value ? 'bg-primary text-white shadow-lg' : 'hover:bg-background/50 text-muted-foreground'
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1 bg-secondary/30 p-1 rounded-lg">
              {[
                { label: 'Общий', value: 'total' },
                { label: 'По категориям', value: 'category' },
                { label: 'По районам', value: 'district' },
                { label: 'По мастерам', value: 'master' }
              ].map((v) => (
                <button
                  key={v.value}
                  onClick={() => setViewMode(v.value)}
                  className={`px-3 py-1 rounded-md text-[10px] font-bold uppercase transition-all ${
                    viewMode === v.value ? 'bg-background text-primary shadow-sm' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Additional Filters Row */}
        <div className="flex flex-wrap items-center gap-4 mb-8 p-4 bg-secondary/20 rounded-xl border border-border/50">
           <div className="flex-1 min-w-[150px]">
             <label className="text-[10px] font-bold text-muted-foreground uppercase mb-1 block">Категория</label>
             <select 
               value={selectedCategory} 
               onChange={(e) => setSelectedCategory(e.target.value)}
               className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary"
             >
               <option value="">Все категории</option>
               {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
             </select>
           </div>

           <div className="flex-1 min-w-[150px]">
             <label className="text-[10px] font-bold text-muted-foreground uppercase mb-1 block">Район</label>
             <select 
               value={selectedDistrict} 
               onChange={(e) => setSelectedDistrict(e.target.value)}
               className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary"
             >
               <option value="">Все районы</option>
               {districts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
             </select>
           </div>

           <div className="flex-1 min-w-[200px]">
             <label className="text-[10px] font-bold text-muted-foreground uppercase mb-1 block">Мастер (только принятые)</label>
             <select 
               value={selectedMasterId} 
               onChange={(e) => setSelectedMasterId(e.target.value)}
               className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary"
             >
               <option value="">Все мастера</option>
               {masters.map(m => <option key={m.id} value={m.id}>{m.full_name} ({m.status})</option>)}
             </select>
           </div>

           {(selectedCategory || selectedDistrict || selectedMasterId) && (
             <button 
               onClick={() => { setSelectedCategory(''); setSelectedDistrict(''); setSelectedMasterId(''); }}
               className="mt-4 md:mt-0 text-[10px] font-bold text-primary hover:underline underline-offset-4"
             >
               Сбросить
             </button>
           )}
        </div>

        {chartRange === 'custom' && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            className="flex flex-wrap items-end gap-4 mb-6 pb-6 border-b border-border"
          >
            <div>
              <label className="text-xs font-bold text-muted-foreground uppercase mb-1 block">От</label>
              <input 
                type="date" 
                value={customDates.start}
                onChange={(e) => setCustomDates({ ...customDates, start: e.target.value })}
                className="bg-secondary/50 border border-border rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-xs font-bold text-muted-foreground uppercase mb-1 block">До</label>
              <input 
                type="date" 
                value={customDates.end}
                onChange={(e) => setCustomDates({ ...customDates, end: e.target.value })}
                className="bg-secondary/50 border border-border rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <button 
              onClick={() => fetchChartData('custom', viewMode, customDates)}
              disabled={!customDates.start || !customDates.end || chartLoading}
              className="px-4 py-1.5 bg-primary hover:bg-primary/90 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-all"
            >
              Применить
            </button>
          </motion.div>
        )}

        <div className="h-[300px] w-full relative">
          {chartLoading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/20 backdrop-blur-[1px]">
               <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary"></div>
            </div>
          )}
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={orderChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis 
                dataKey="date" 
                stroke="#94a3b8" 
                fontSize={12} 
                tickLine={false} 
                axisLine={false}
              />
              <YAxis 
                stroke="#94a3b8" 
                fontSize={12} 
                tickLine={false} 
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                itemStyle={{ fontWeight: 'bold' }}
              />
              <Legend 
                verticalAlign="bottom" 
                align="center" 
                iconType="circle"
                wrapperStyle={{ paddingTop: '20px' }}
              />
              {seriesNames.map((name, index) => (
                <Line 
                  key={name}
                  type="monotone" 
                  dataKey={name} 
                  stroke={getLineColor(index)} 
                  strokeWidth={viewMode === 'total' ? 3 : 2} 
                  dot={viewMode === 'total' ? { r: 4, fill: getLineColor(index), stroke: '#0f172a' } : false} 
                  activeDot={{ r: 6, strokeWidth: 0 }}
                  animationDuration={1500}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Status Breakdown */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-6 rounded-2xl"
        >
          <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-primary" />
            Статусы заказов
          </h2>
          <div className="h-[250px] w-full min-h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={stats.order_status_distribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {stats.order_status_distribution.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={['#6366f1', '#10b981', '#f59e0b', '#ef4444'][index % 4]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-3 mt-4">
            {stats.order_status_distribution.map((item: any, i: number) => (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ['#6366f1', '#10b981', '#f59e0b', '#ef4444'][i % 4] }} />
                  <span className="text-sm text-muted-foreground">{item.name}</span>
                </div>
                <span className="font-bold">{item.value}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Categories Breakdown */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="lg:col-span-2 glass-card p-6 rounded-2xl"
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <ShoppingBag className="w-5 h-5 text-primary" />
              Заказы по категориям
            </h2>
          </div>
          <div className="h-[350px] w-full min-h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.categories_breakdown} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                <XAxis type="number" stroke="#94a3b8" />
                <YAxis dataKey="name" type="category" stroke="#94a3b8" width={120} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                  itemStyle={{ color: '#f8fafc' }}
                />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 8, 8, 0]} label={{ position: 'right', fill: '#94a3b8' }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Districts Breakdown */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass-card p-6 rounded-2xl"
        >
          <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-primary" />
            Топ районов
          </h2>
          <div className="space-y-6">
            {stats.districts_breakdown.map((d: any, i: number) => (
              <div key={d.name} className="relative">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{d.name}</span>
                  <span className="text-sm text-primary font-bold">{d.count}</span>
                </div>
                <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${(d.count / (stats.districts_breakdown[0]?.count || 1)) * 100}%` }}
                    className="h-full bg-primary"
                  />
                </div>
              </div>
            ))}
            {stats.districts_breakdown.length === 0 && (
              <p className="text-muted-foreground text-center py-10">Нет данных по районам</p>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}

function StatCard({ icon, title, value, subtitle, highlight = false }: any) {
  return (
    <motion.div 
      whileHover={{ y: -5 }}
      className={`glass-card p-6 rounded-2xl border-l-4 ${highlight ? 'border-l-primary' : 'border-l-transparent'}`}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="p-2 bg-secondary rounded-lg">
          {icon}
        </div>
        {highlight && (
          <span className="bg-primary/20 text-primary text-[10px] uppercase font-bold px-2 py-1 rounded-full">
            Внимание
          </span>
        )}
      </div>
      <div>
        <p className="text-muted-foreground text-sm font-medium">{title}</p>
        <h3 className="text-3xl font-bold mt-1">{value}</h3>
        <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
          {subtitle.includes('ожидают') && <Hourglass className="w-3 h-3" />}
          {subtitle}
        </p>
      </div>
    </motion.div>
  );
}
