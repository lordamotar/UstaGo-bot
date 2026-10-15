import api from '@/lib/api';

/** Скачивает CSV с API (нужен заголовок Authorization, поэтому не обычная ссылка). */
export async function downloadCsv(path: string, params: Record<string, unknown>, filename: string) {
  const res = await api.get(path, { params, responseType: 'blob' });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const fmtDate = (v?: string | null) =>
  v ? new Date(v.endsWith('Z') || v.includes('+') ? v : v + 'Z').toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '—';
