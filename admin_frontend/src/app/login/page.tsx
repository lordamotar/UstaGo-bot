'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ShieldCheck, Key } from 'lucide-react';
import { motion } from 'framer-motion';

export default function LoginPage() {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Пробуем вызвать эндпоинт stats для проверки ключа
      const response = await fetch('http://127.0.0.1:8000/api/v1/health');
      
      // На самом деле для проверки ключа нам нужно сделать запрос к защищенному эндпоинту
      const checkResponse = await fetch('http://127.0.0.1:8000/api/v1/stats', {
        headers: { 'X-API-Key': apiKey }
      });

      if (checkResponse.ok) {
        localStorage.setItem('admin_api_key', apiKey);
        router.push('/');
      } else {
        setError('Неверный API-ключ. Доступ запрещен.');
      }
    } catch (err) {
      setError('Ошибка соединения с сервером API.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-indigo-900/20 via-background to-background">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md glass-card p-8 rounded-2xl shadow-2xl space-y-8"
      >
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="p-3 bg-primary/10 rounded-full">
              <ShieldCheck className="w-10 h-10 text-primary" />
            </div>
          </div>
          <h1 className="text-3xl font-bold gradient-text">UstaGo Admin</h1>
          <p className="text-muted-foreground">Введите секретный ключ для доступа к панели</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium ml-1">Секретный ключ</label>
            <div className="relative">
              <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="password"
                required
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full bg-secondary/50 border border-border rounded-xl py-3 pl-10 pr-4 focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                placeholder="Ваш ADMIN_API_KEY"
              />
            </div>
          </div>

          {error && (
            <motion.p 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-destructive text-sm text-center font-medium"
            >
              {error}
            </motion.p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary hover:bg-primary/90 text-white font-bold py-3 rounded-xl shadow-lg shadow-primary/20 transition-all active:scale-95 disabled:opacity-50"
          >
            {loading ? 'Проверка...' : 'Войти в систему'}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
