'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { ROLE_LABEL, useMe } from '@/lib/useMe';
import { ArrowLeft, ShieldCheck } from 'lucide-react';

type Admin = { id: number; username: string | null; full_name: string; telegram_id: number; admin_role: string; has_password: boolean };

const HINT: Record<string, string> = {
  superadmin: 'Всё, включая настройки, справочники, логи, бэкапы и роли',
  moderator: 'Мастера (одобрение, бан, аккредитация) и отмена заказов',
  finance: 'Баллы и заявки на пополнение',
};

export default function AdminsPage() {
  const router = useRouter();
  const { me, can } = useMe();
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [error, setError] = useState('');

  const load = () => api.get('/admins').then((r) => setAdmins(r.data)).catch((e) => setError(e?.response?.data?.detail || 'Нет доступа'));
  useEffect(() => { load(); }, []);

  const setRole = async (a: Admin, role: string) => {
    if (role === a.admin_role) return;
    if (!window.confirm(`Сменить роль ${a.username || a.full_name}: ${ROLE_LABEL[a.admin_role]} → ${ROLE_LABEL[role]}?`)) return;
    try { await api.patch(`/admins/${a.id}`, { admin_role: role }); await load(); }
    catch (e: any) { alert(e?.response?.data?.detail || 'Ошибка'); }
  };

  return (
    <div className="min-h-screen bg-background p-6 lg:p-10">
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors"><ArrowLeft className="w-6 h-6" /></button>
        <h1 className="text-3xl font-bold flex items-center gap-2"><ShieldCheck className="w-7 h-7 text-primary" />Администраторы</h1>
      </div>
      {error && <p className="text-red-400 mb-6">{error}</p>}
      {!can.superadmin && me && <p className="text-muted-foreground">Раздел доступен только суперадмину.</p>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {Object.keys(HINT).map((r) => (
          <div key={r} className="glass-card p-4 rounded-xl border border-border">
            <p className="font-bold">{ROLE_LABEL[r]}</p>
            <p className="text-sm text-muted-foreground mt-1">{HINT[r]}</p>
          </div>
        ))}
      </div>
      <div className="glass-card rounded-2xl overflow-hidden border border-border">
        <table className="w-full text-left">
          <thead className="bg-secondary/30 border-b border-border">
            <tr>{['Логин', 'Имя', 'Telegram ID', 'Роль'].map((h) => <th key={h} className="px-6 py-4 text-sm font-semibold text-muted-foreground">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-border">
            {admins.map((a) => (
              <tr key={a.id}>
                <td className="px-6 py-4 font-bold">{a.username || '—'}{!a.has_password && <span className="ml-2 text-xs text-orange-400">нет пароля</span>}</td>
                <td className="px-6 py-4">{a.full_name}</td>
                <td className="px-6 py-4 text-sm text-muted-foreground">{a.telegram_id}</td>
                <td className="px-6 py-4">
                  <select value={a.admin_role} onChange={(e) => setRole(a, e.target.value)}
                    className="bg-secondary/50 border border-border rounded-lg px-3 py-1.5 text-sm outline-none">
                    {Object.keys(ROLE_LABEL).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground mt-4">Новый администратор создаётся командой на сервере: <code>python scripts/set_admin.py логин пароль moderator</code>. Свою роль менять нельзя.</p>
    </div>
  );
}
