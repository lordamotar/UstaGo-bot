'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { 
  ArrowLeft, 
  Database,
  Download,
  Trash2,
  Plus,
  FileCode,
  Calendar,
  HardDrive
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function BackupsPage() {
  const [backups, setBackups] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const router = useRouter();

  const fetchBackups = async () => {
    try {
      setLoading(true);
      const res = await api.get('/backups');
      setBackups(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBackups();
  }, []);

  const handleCreateBackup = async () => {
    try {
      setCreating(true);
      await api.post('/backups');
      await fetchBackups();
    } catch (err) {
      console.error(err);
      alert('Ошибка при создании бэкапа');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteBackup = async (filename: string) => {
    if (!confirm(`Вы уверены, что хотите удалить бэкап ${filename}?`)) return;
    try {
      await api.delete(`/backups/${filename}`);
      setBackups(backups.filter(b => b.filename !== filename));
    } catch (err) {
      console.error(err);
      alert('Ошибка при удалении');
    }
  };

  const handleDownload = (filename: string) => {
    const token = localStorage.getItem('admin_token');
    // Using simple window.open or a temporary link for download
    const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/backups/${filename}?token=${token}`;
    window.open(url, '_blank');
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="min-h-screen bg-background text-foreground p-6 lg:p-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div className="flex items-center gap-4">
          <button onClick={() => router.push('/')} className="p-2 hover:bg-secondary rounded-full transition-colors">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Database className="w-8 h-8 text-primary" />
            Резервные копии (Бэкапы)
          </h1>
        </div>
        
        <button 
          onClick={handleCreateBackup}
          disabled={creating}
          className="flex items-center gap-2 px-6 py-2.5 bg-primary hover:bg-primary/90 text-white rounded-xl transition-all shadow-lg shadow-primary/20 disabled:opacity-50"
        >
          {creating ? (
            <div className="w-4 h-4 border-2 border-white/30 border-t-white animate-spin rounded-full" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          Создать бэкап сейчас
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <div className="glass-card p-6 rounded-2xl flex items-center gap-4">
          <div className="p-3 bg-blue-500/10 rounded-xl">
             <FileCode className="w-6 h-6 text-blue-500" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Всего копий</p>
            <h3 className="text-2xl font-bold">{backups.length}</h3>
          </div>
        </div>
        <div className="glass-card p-6 rounded-2xl flex items-center gap-4">
          <div className="p-3 bg-green-500/10 rounded-xl">
             <HardDrive className="w-6 h-6 text-green-500" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Общий объем</p>
            <h3 className="text-2xl font-bold">
              {formatSize(backups.reduce((acc, curr) => acc + curr.size, 0))}
            </h3>
          </div>
        </div>
        <div className="glass-card p-6 rounded-2xl flex items-center gap-4">
          <div className="p-3 bg-purple-500/10 rounded-xl">
             <Calendar className="w-6 h-6 text-purple-500" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Последний бэкап</p>
            <h3 className="text-base font-bold">
              {backups.length > 0 ? new Date(backups[0].created_at).toLocaleDateString() : 'Нет данных'}
            </h3>
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
                  <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Файл</th>
                  <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Дата создания</th>
                  <th className="px-6 py-4 text-sm font-semibold text-muted-foreground">Размер</th>
                  <th className="px-6 py-4 text-sm font-semibold text-muted-foreground text-right">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <AnimatePresence>
                  {backups.map((b) => (
                    <motion.tr 
                      key={b.filename}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="hover:bg-secondary/20 transition-colors"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <Database className="w-5 h-5 text-muted-foreground" />
                          <span className="font-medium">{b.filename}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {new Date(b.created_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 text-sm">
                        {formatSize(b.size)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button 
                            onClick={() => handleDownload(b.filename)}
                            className="p-2 hover:bg-primary/20 text-primary rounded-lg transition-colors"
                            title="Скачать"
                          >
                            <Download className="w-5 h-5" />
                          </button>
                          <button 
                            onClick={() => handleDeleteBackup(b.filename)}
                            className="p-2 hover:bg-red-500/20 text-red-500 rounded-lg transition-colors"
                            title="Удалить"
                          >
                            <Trash2 className="w-5 h-5" />
                          </button>
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
            
            {backups.length === 0 && (
              <div className="p-20 text-center text-muted-foreground">
                Бэкапов не найдено
              </div>
            )}
          </div>
        </div>
      )}
      
      <div className="mt-8 p-6 bg-secondary/20 rounded-2xl border border-border">
        <h4 className="font-bold flex items-center gap-2 mb-2">
          <Database className="w-4 h-4 text-primary" />
          Автоматизация
        </h4>
        <p className="text-sm text-muted-foreground">
          Система автоматически создает резервную копию каждые 24 часа при запуске API сервера. 
          Хранятся последние 10 копий. Все файлы сохраняются в формате JSON для обеспечения переносимости данных.
        </p>
      </div>
    </div>
  );
}
