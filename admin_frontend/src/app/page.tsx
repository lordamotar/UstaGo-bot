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
  Settings
} from 'lucide-react';
import ChangePasswordModal from '@/components/ChangePasswordModal';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { motion } from 'framer-motion';

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const key = localStorage.getItem('admin_token');
    if (!key) {
      router.push('/login');
      return;
    }

    const fetchStats = async () => {
      try {
        const response = await api.get('/stats');
        setStats(response.data);
      } catch (err) {
        console.error(err);
        localStorage.removeItem('admin_token');
        router.push('/login');
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [router]);

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
          title="Активных заказов" 
          value={stats.orders.active} 
          subtitle={`${stats.orders.new} новых заявок`}
        />
        <StatCard 
          icon={<TrendingUp className="text-green-400" />} 
          title="Эффективность" 
          value="84%" 
          subtitle="+12% за неделю"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Chart */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="lg:col-span-2 glass-card p-6 rounded-2xl"
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary" />
              Распределение пользователей
            </h2>
          </div>
          <div className="h-[300px] w-full min-h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                  itemStyle={{ color: '#f8fafc' }}
                />
                <Bar dataKey="value" fill="#6366f1" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Status Breakdown */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-6 rounded-2xl"
        >
          <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-primary" />
            Доля ролей
          </h2>
          <div className="h-[250px] w-full min-h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-3 mt-4">
            {chartData.map((item, i) => (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[i] }} />
                  <span className="text-sm text-muted-foreground">{item.name}</span>
                </div>
                <span className="font-bold">{item.value}</span>
              </div>
            ))}
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
