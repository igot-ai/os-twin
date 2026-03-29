'use client';

import { useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useUIStore } from '@/lib/stores/uiStore';

const navItems = [
  { href: '/', icon: 'grid_view', label: 'Dashboard' },
  { href: '/plans', icon: 'folder', label: 'Plans' },
  { href: '/roles', icon: 'person', label: 'Roles' },
  { href: '/skills', icon: 'extension', label: 'Skills' },
  { href: '/settings', icon: 'settings', label: 'Settings' },
];

export default function Sidebar({ className = '', ...props }: React.ComponentPropsWithoutRef<'aside'>) {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  // Auto-collapse logic for 1024px - 1280px
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      if (width >= 1024 && width <= 1280) {
        if (!sidebarCollapsed) {
          useUIStore.setState({ sidebarCollapsed: true });
        }
      } else if (width > 1280) {
        if (sidebarCollapsed) {
          useUIStore.setState({ sidebarCollapsed: false });
        }
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize(); // Initial check
    return () => window.removeEventListener('resize', handleResize);
  }, [sidebarCollapsed]);

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <aside
      {...props}
      className={`shrink-0 flex flex-col border-r transition-all duration-200 ease-out overflow-hidden ${className}`}
      style={{
        width: sidebarCollapsed ? 64 : 240,
        minWidth: sidebarCollapsed ? 64 : 240,
        background: 'var(--color-surface)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* Logo */}
      <div
        className="h-14 flex items-center gap-3 px-4 border-b shrink-0"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <Image
          src="/logo.svg"
          alt="OsTwin"
          width={32}
          height={32}
          className="shrink-0"
          aria-hidden="true"
        />
        {!sidebarCollapsed && (
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-bold truncate" style={{ color: 'var(--color-text-main)' }}>
              Os<span style={{ background: 'linear-gradient(135deg, #00ff88, #00c4e0, #00d4ff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Twin</span>
            </span>
            <span className="text-[10px]" style={{ color: 'var(--color-text-faint)' }}>Command Center</span>
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto custom-scrollbar">
        {navItems.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              prefetch={false}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group relative"
              style={{
                color: active ? 'var(--color-primary)' : 'var(--color-text-muted)',
                background: active ? 'var(--color-primary-muted)' : 'transparent',
              }}
              title={sidebarCollapsed ? item.label : undefined}
              aria-label={item.label}
              aria-current={active ? 'page' : undefined}
            >
              {active && (
                <div
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                  style={{ background: 'var(--color-primary)' }}
                />
              )}
              <span className="material-symbols-outlined text-xl" style={{ fontSize: 20 }} aria-hidden="true">
                {item.icon}
              </span>
              {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div
        className="px-2 py-3 border-t shrink-0"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <span className="material-symbols-outlined text-lg" aria-hidden="true">
            {sidebarCollapsed ? 'chevron_right' : 'chevron_left'}
          </span>
          {!sidebarCollapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
