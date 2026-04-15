'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ShieldCheck, User, Lock, KeyRound } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '@/lib/api';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [twoFACode, setTwoFACode] = useState('');
  const [step, setStep] = useState<'credentials' | '2fa'>('credentials');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await api.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      if (response.data.requires_2fa) {
        // Move to 2FA step
        setStep('2fa');
      } else if (response.data.access_token) {
        localStorage.setItem('admin_token', response.data.access_token);
        router.push('/');
      }
    } catch (err: any) {
      if (err.response && err.response.status === 401) {
        setError('Неверный логин или пароль.');
      } else if (err.response && err.response.status === 500) {
        setError('Не удалось отправить код в Telegram. Проверьте бота.');
      } else {
        setError('Ошибка при входе. Проверьте соединение с сервером.');
      }
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify2FA = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await api.post('/auth/verify-2fa', {
        username,
        code: twoFACode,
      });

      if (response.data.access_token) {
        localStorage.setItem('admin_token', response.data.access_token);
        router.push('/');
      }
    } catch (err: any) {
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Ошибка проверки кода.');
      }
      console.error(err);
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
          <p className="text-muted-foreground">
            {step === 'credentials' 
              ? 'Войдите в систему управления' 
              : '🔐 Введите код из Telegram'}
          </p>
        </div>

        <AnimatePresence mode="wait">
          {step === 'credentials' ? (
            <motion.form 
              key="credentials"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              onSubmit={handleLogin} 
              className="space-y-6"
            >
              <div className="space-y-2">
                <label className="text-sm font-medium ml-1">Логин</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full bg-secondary/50 border border-border rounded-xl py-3 pl-10 pr-4 focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                    placeholder="Имя пользователя"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium ml-1">Пароль</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-secondary/50 border border-border rounded-xl py-3 pl-10 pr-4 focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                    placeholder="••••••••"
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
                {loading ? 'Вход...' : 'Войти в панель'}
              </button>
            </motion.form>
          ) : (
            <motion.form 
              key="2fa"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              onSubmit={handleVerify2FA} 
              className="space-y-6"
            >
              <div className="p-4 bg-primary/5 border border-primary/20 rounded-xl text-center">
                <KeyRound className="w-8 h-8 text-primary mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">
                  Мы отправили 6-значный код в ваш Telegram. 
                  Введите его ниже для завершения входа.
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium ml-1">Код подтверждения</label>
                <div className="relative">
                  <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <input
                    type="text"
                    required
                    maxLength={6}
                    value={twoFACode}
                    onChange={(e) => setTwoFACode(e.target.value.replace(/\D/g, ''))}
                    className="w-full bg-secondary/50 border border-border rounded-xl py-3 pl-10 pr-4 focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all text-center text-2xl tracking-[0.5em] font-mono"
                    placeholder="••••••"
                    autoFocus
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
                disabled={loading || twoFACode.length !== 6}
                className="w-full bg-primary hover:bg-primary/90 text-white font-bold py-3 rounded-xl shadow-lg shadow-primary/20 transition-all active:scale-95 disabled:opacity-50"
              >
                {loading ? 'Проверка...' : 'Подтвердить'}
              </button>

              <button
                type="button"
                onClick={() => { setStep('credentials'); setError(''); setTwoFACode(''); }}
                className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                ← Вернуться к логину
              </button>
            </motion.form>
          )}
        </AnimatePresence>
        
        <div className="text-center">
          <p className="text-xs text-muted-foreground pt-4 border-t border-border">
            {step === 'credentials' 
              ? 'Если вы забыли данные, обратитесь к системному администратору'
              : 'Код действителен 5 минут'}
          </p>
        </div>
      </motion.div>
    </div>
  );
}
