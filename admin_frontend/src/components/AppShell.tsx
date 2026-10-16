'use client';

import { usePathname } from 'next/navigation';
import Sidebar from '@/components/Sidebar';

/** Боковая панель на всех страницах, кроме входа. */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname.startsWith('/login')) return <>{children}</>;
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 pt-14 lg:pt-0">{children}</main>
    </div>
  );
}
