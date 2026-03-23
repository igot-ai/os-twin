'use client';

import { Suspense } from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import Image from 'next/image';
import { useProjects } from '@/hooks/useProjects';

const PROJECT_COLORS = [
  'var(--purple)',
  'var(--cyan)',
  'var(--green)',
  'var(--amber)',
  'var(--orange)',
  'var(--red)',
  '#6ee7b7',
  '#93c5fd',
];

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  connected: boolean;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  summary: { active: number; passed: number; total: number };
}

interface NavItem {
  href: string;
  icon: string;
  label: string;
}

const WORK_ITEMS: NavItem[] = [
  { href: '/', icon: '⬡', label: 'Dashboard' },
];

const AGENT_ITEMS: NavItem[] = [
  { href: '/agents?role=manager', icon: '⬡', label: 'Manager' },
  { href: '/agents?role=engineer', icon: '⚙', label: 'Engineer' },
  { href: '/agents?role=qa', icon: '✦', label: 'QA' },
  { href: '/agents?role=architect', icon: '◆', label: 'Architect' },
  { href: '/agents?role=reporter', icon: '📊', label: 'Reporter' },
  { href: '/agents?role=audit', icon: '🔍', label: 'Audit' },
];

const SYSTEM_ITEMS: NavItem[] = [
  { href: '/skills', icon: '◈', label: 'Skills' },
  { href: '/warrooms', icon: '⬢', label: 'War Rooms' },
  { href: '/settings', icon: '⚙', label: 'Settings' },
];

function NavLink({
  item,
  pathname,
  collapsed,
}: {
  item: NavItem;
  pathname: string;
  collapsed: boolean;
}) {
  const searchParams = useSearchParams();
  const hrefUrl = new URL(item.href, 'http://x');
  const hrefPath = hrefUrl.pathname;
  const hrefParams = hrefUrl.searchParams;

  let isActive: boolean;
  if (item.href === '/') {
    isActive = pathname === '/';
  } else if (hrefParams.size > 0) {
    isActive =
      pathname === hrefPath &&
      Array.from(hrefParams.entries()).every(
        ([key, value]) => searchParams.get(key) === value,
      );
  } else {
    isActive = pathname.startsWith(hrefPath);
  }

  return (
    <Link
      href={item.href}
      className={`sidebar-item${isActive ? ' active' : ''}`}
      title={collapsed ? item.label : undefined}
    >
      <span className="sidebar-item-icon">{item.icon}</span>
      {!collapsed && <span className="sidebar-item-label">{item.label}</span>}
    </Link>
  );
}

export default function Sidebar(props: SidebarProps) {
  return (
    <Suspense>
      <SidebarInner {...props} />
    </Suspense>
  );
}

function SidebarInner({
  collapsed,
  onToggleCollapse,
  connected,
  theme,
  onToggleTheme,
  summary,
}: SidebarProps) {
  const pathname = usePathname();
  const { projects } = useProjects();

  return (
    <aside className={`sidebar${collapsed ? ' sidebar-collapsed' : ''}`}>
      <div className="sidebar-header">
        <Link href="/" className="sidebar-logo">
          <Image src="/assets/logo.svg" className="logo-img" alt="OS Twin" width={18} height={18} />
          {!collapsed && (
            <>
              <span className="logo-text">
                OS<span className="logo-accent">TWIN</span>
              </span>
              <span className="logo-version">v0.1.0</span>
            </>
          )}
        </Link>
      </div>

      <div className="sidebar-nav">
        <div className="sidebar-section">
          <div className="sidebar-section-title">{!collapsed && 'WORK'}</div>
          {WORK_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} collapsed={collapsed} />
          ))}
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">
            {!collapsed && 'PROJECTS'}
            {!collapsed && (
              <Link href="/projects" className="sidebar-section-action" title="View projects">
                +
              </Link>
            )}
          </div>
          {projects.length > 0 ? (
            projects.map((project, i) => (
              <Link
                key={project.path}
                href="/projects"
                className={`sidebar-item${pathname === '/projects' ? '' : ''}`}
                title={collapsed ? project.name : project.path}
              >
                <span
                  className="sidebar-item-icon project-dot-sm"
                  style={{ color: PROJECT_COLORS[i % PROJECT_COLORS.length] }}
                >
                  ●
                </span>
                {!collapsed && <span className="sidebar-item-label">{project.name}</span>}
              </Link>
            ))
          ) : (
            <NavLink
              item={{ href: '/projects', icon: '◆', label: 'All Projects' }}
              pathname={pathname}
              collapsed={collapsed}
            />
          )}
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">{!collapsed && 'AGENTS'}</div>
          {AGENT_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} collapsed={collapsed} />
          ))}
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">{!collapsed && 'SYSTEM'}</div>
          {SYSTEM_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} collapsed={collapsed} />
          ))}
        </div>
      </div>

      <div className="sidebar-footer">
        {!collapsed && (
          <div className="sidebar-stats">
            <span className="sidebar-stat">
              <span className={`stat-dot${summary.active > 0 ? ' active-dot' : ''}`}></span>
              {summary.active}
            </span>
            <span className="sidebar-stat">
              <span style={{ color: 'var(--green)' }}>✓</span>
              {summary.passed}
            </span>
            <span className="sidebar-stat">
              <span style={{ color: 'var(--text-dim)' }}>⬡</span>
              {summary.total}
            </span>
          </div>
        )}
        <div className="sidebar-actions">
          <span className={`conn-dot${connected ? ' connected' : ' disconnected'}`}></span>
          {!collapsed && (
            <span style={{ color: connected ? '#00ff8888' : '#ff6b6b88', fontSize: '9px' }}>
              {connected ? 'LIVE' : 'OFFLINE'}
            </span>
          )}
          <button className="sidebar-action-btn" onClick={onToggleTheme} title="Toggle theme">
            {theme === 'dark' ? '🌙' : '☀️'}
          </button>
          <button className="sidebar-action-btn" onClick={onToggleCollapse} title="Toggle sidebar">
            {collapsed ? '▸' : '◂'}
          </button>
        </div>
      </div>
    </aside>
  );
}
