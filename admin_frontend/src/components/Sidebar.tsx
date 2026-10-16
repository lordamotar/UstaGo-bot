'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import api from '@/lib/api';
import { ROLE_LABEL, useMe } from '@/lib/useMe';
import ChangePasswordModal from '@/components/ChangePasswordModal';
import {
  LayoutDashboard, Users, ShoppingBag, LifeBuoy, Megaphone, CreditCard, MapPin, History, Database,
  ShieldCheck, KeyRound, LogOut, PanelLeftClose, PanelLeftOpen, Menu, X,
} from 'lucide-react';

type Item = { href: string; label: string; icon: any; show?: boolean; badge?: number };

const STORAGE_KEY = 'sidebar_collapsed';

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { me, can } = useMe();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openTickets, setOpenTickets] = useState(0);
  const [passwordOpen, setPasswordOpen] = useState(false);

  // запомненное состояние читаем после монтирования (на сервере localStorage нет)
  useEffect(() => {
    try { setCollapsed(localStorage.getItem(STORAGE_KEY) === '1'); } catch { /* приватный режим */ }
  }, []);
  const toggle = () => {
    setCollapsed((c) => {
      try { localStorage.setItem(STORAGE_KEY, c ? '0' : '1'); } catch { /* ничего страшного */ }
      return !c;
    });
  };

  useEffect(() => { setMobileOpen(false); }, [pathname]);

  // бейдж «обращений без ответа»: обновляем при смене страницы и раз в минуту
  useEffect(() => {
    let alive = true;
    const load = () => api.get('/stats').then((r) => { if (alive) setOpenTickets(r.data?.moderation?.open_tickets ?? 0); }).catch(() => {});
    load();
    const t = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(t); };
  }, [pathname]);

  const logout = () => {
    try { localStorage.removeItem('admin_token'); } catch { /* ignore */ }
    router.push('/login');
  };

  const main: Item[] = [
    { href: '/', label: 'Главная', icon: LayoutDashboard },
    { href: '/users', label: 'Пользователи', icon: Users },
    { href: '/orders', label: 'Заказы', icon: ShoppingBag },
    { href: '/support', label: 'Поддержка', icon: LifeBuoy, badge: openTickets },
    { href: '/acquisition', label: 'Источники', icon: Megaphone },
    { href: '/finances', label: 'Финансы', icon: CreditCard, show: can.finance },
  ];
  const admin: Item[] = [
    { href: '/directories', label: 'Справочники', icon: MapPin, show: can.superadmin },
    { href: '/logs', label: 'Логи', icon: History, show: can.superadmin },
    { href: '/backups', label: 'Бэкапы', icon: Database, show: can.superadmin },
    { href: '/admins', label: 'Админы', icon: ShieldCheck, show: can.superadmin },
  ];

  const isActive = (href: string) => (href === '/' ? pathname === '/' : pathname.startsWith(href));

  const renderItem = (it: Item, wide: boolean) => {
    const Icon = it.icon;
    return (
      <Link key={it.href} href={it.href} title={wide ? undefined : it.label}
        className={`relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${isActive(it.href) ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'} ${wide ? '' : 'justify-center'}`}>
        <Icon className="w-5 h-5 shrink-0" />
        {wide && <span className="truncate">{it.label}</span>}
        {!!it.badge && it.badge > 0 && (wide
          ? <span className="ml-auto min-w-5 h-5 px-1.5 rounded-full bg-orange-500 text-white text-[11px] font-bold flex items-center justify-center">{it.badge}</span>
          : <span className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-orange-500" />)}
      </Link>
    );
  };

  const panel = (wide: boolean) => (
    <div className="h-full flex flex-col">
      <div className={`flex items-center ${wide ? 'justify-between' : 'justify-center'} px-4 h-16 shrink-0`}>
        {wide && <Link href="/" className="text-lg font-extrabold gradient-text">UstaGo Admin</Link>}
        <button onClick={toggle} title={wide ? 'Свернуть' : 'Развернуть'}
          className="hidden lg:flex p-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors">
          {wide ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeftOpen className="w-5 h-5" />}
        </button>
        <button onClick={() => setMobileOpen(false)} className="lg:hidden p-2 rounded-lg hover:bg-secondary"><X className="w-5 h-5" /></button>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        {main.filter((i) => i.show !== false).map((i) => renderItem(i, wide))}
        {admin.some((i) => i.show) && (
          <>
            <div className={`pt-4 pb-1 px-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground/70 ${wide ? '' : 'text-center px-0'}`}>
              {wide ? 'Администрирование' : '···'}
            </div>
            {admin.filter((i) => i.show).map((i) => renderItem(i, wide))}
          </>
        )}
      </nav>

      <div className="border-t border-border p-3 space-y-1 shrink-0">
        {wide && me && (
          <div className="px-3 pb-2">
            <p className="text-sm font-bold truncate">{me.full_name}</p>
            <p className="text-xs text-muted-foreground">{ROLE_LABEL[me.admin_role]}</p>
          </div>
        )}
        <button onClick={() => setPasswordOpen(true)} title={wide ? undefined : 'Сменить пароль'}
          className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors ${wide ? '' : 'justify-center'}`}>
          <KeyRound className="w-5 h-5 shrink-0" />{wide && 'Сменить пароль'}
        </button>
        <button onClick={logout} title={wide ? undefined : 'Выйти'}
          className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-red-500/10 hover:text-red-400 transition-colors ${wide ? '' : 'justify-center'}`}>
          <LogOut className="w-5 h-5 shrink-0" />{wide && 'Выйти'}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* телефон: кнопка-«бургер» и выезжающая панель */}
      <button onClick={() => setMobileOpen(true)} aria-label="Меню"
        className="lg:hidden fixed top-3 left-3 z-40 p-2 rounded-xl bg-secondary border border-border shadow-lg">
        <Menu className="w-5 h-5" />
        {openTickets > 0 && <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-orange-500" />}
      </button>
      {mobileOpen && <div className="lg:hidden fixed inset-0 z-40 bg-black/60" onClick={() => setMobileOpen(false)} />}
      <aside className={`lg:hidden fixed inset-y-0 left-0 z-50 w-64 bg-background border-r border-border transition-transform ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        {panel(true)}
      </aside>

      {/* компьютер: постоянная боковая панель, сворачивается до иконок */}
      <aside className={`hidden lg:block sticky top-0 h-screen shrink-0 bg-background border-r border-border transition-[width] duration-200 ${collapsed ? 'w-[72px]' : 'w-64'}`}>
        {panel(!collapsed)}
      </aside>

      <ChangePasswordModal isOpen={passwordOpen} onClose={() => setPasswordOpen(false)} />
    </>
  );
}
