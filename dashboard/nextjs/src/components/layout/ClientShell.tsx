'use client';

import { useState } from 'react';
import { AppProvider, useApp } from '@/contexts/AppContext';
import AuthOverlay from '@/components/shared/AuthOverlay';
import Sidebar from '@/components/layout/Sidebar';
import ReleaseBar from '@/components/layout/ReleaseBar';
import PlanEditor from '@/components/plan/PlanEditor';

function ShellInner({ children }: { children: React.ReactNode }) {
  const app = useApp();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <>
      <AuthOverlay show={app.showLogin} onLogin={app.performLogin} error={app.authError} />

      <div className="app-shell">
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((p) => !p)}
          connected={app.connected}
          theme={app.theme}
          onToggleTheme={app.toggleTheme}
          summary={app.summary}
        />
        <main className="app-content">{children}</main>
      </div>

      {app.activeEditorPlanId && (
        <PlanEditor planId={app.activeEditorPlanId} onClose={app.closePlanEditor} />
      )}

      <ReleaseBar content={app.releaseContent} />
    </>
  );
}

export default function ClientShell({ children }: { children: React.ReactNode }) {
  return (
    <AppProvider>
      <ShellInner>{children}</ShellInner>
    </AppProvider>
  );
}
