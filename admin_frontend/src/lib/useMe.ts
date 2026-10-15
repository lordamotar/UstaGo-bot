import { useEffect, useState } from 'react';
import api from '@/lib/api';

export type AdminRole = 'superadmin' | 'moderator' | 'finance';

let cached: { admin_role: AdminRole; full_name: string } | null = null;
let cachedToken: string | null = null; // кэш привязан к токену: после смены аккаунта роль перезапрашивается

/** Текущий админ и то, что ему можно. Сервер всё равно проверяет права — это только скрывает лишние кнопки. */
export function useMe() {
  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_token') : null;
  if (cachedToken !== token) { cached = null; cachedToken = token; }
  const [me, setMe] = useState(cached);
  useEffect(() => {
    if (cached || !token) return;
    api.get('/auth/me').then((r) => { cached = r.data; cachedToken = token; setMe(r.data); }).catch(() => {});
  }, [token]);
  const role = me?.admin_role;
  return {
    me,
    can: {
      moderate: role === 'superadmin' || role === 'moderator',
      finance: role === 'superadmin' || role === 'finance',
      superadmin: role === 'superadmin',
    },
  };
}

export const ROLE_LABEL: Record<string, string> = {
  superadmin: 'Суперадмин', moderator: 'Модератор', finance: 'Финансист',
};
