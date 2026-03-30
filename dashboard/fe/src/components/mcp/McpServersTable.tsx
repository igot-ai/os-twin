import React, { useState } from 'react';
import { useMcpServers, McpServer } from '@/hooks/use-mcp';
import { CredentialManager } from './CredentialManager';

const typeBranding: Record<string, { bg: string; text: string; icon: string }> = {
  stdio: { bg: 'bg-amber-50', text: 'text-amber-700', icon: 'terminal' },
  http: { bg: 'bg-violet-50', text: 'text-violet-700', icon: 'cloud' },
};

export const McpServersTable: React.FC = () => {
  const { servers, isLoading, isError, removeServer, testServer, refresh } = useMcpServers();
  const [testingStatus, setTestingStatus] = useState<Record<string, { status: string; message: string }>>({});
  const [expandedServer, setExpandedServer] = useState<string | null>(null);

  const handleTest = async (name: string) => {
    setTestingStatus(prev => ({ ...prev, [name]: { status: 'testing', message: 'Testing...' } }));
    try {
      const res = await testServer(name);
      setTestingStatus(prev => ({ ...prev, [name]: { status: res.status, message: res.message } }));
    } catch (e) {
      setTestingStatus(prev => ({ ...prev, [name]: { status: 'error', message: 'Failed to test' } }));
    }
  };

  const handleDelete = async (name: string) => {
    if (confirm(`Are you sure you want to remove ${name}?`)) {
      await removeServer(name);
      refresh();
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-20 animate-pulse">
        <div className="w-12 h-12 rounded-full bg-slate-100 mb-4 flex items-center justify-center">
          <span className="material-symbols-outlined text-text-faint animate-spin">refresh</span>
        </div>
        <p className="text-sm font-bold text-text-faint uppercase tracking-widest">Loading servers...</p>
      </div>
    );
  }

  if (isError) return <div className="p-8 text-red-500">Failed to load MCP servers</div>;

  if (!servers || servers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-20 text-center border-2 border-dashed rounded-2xl bg-slate-50/30 border-border">
        <div className="w-16 h-16 rounded-2xl bg-surface shadow-sm mb-6 flex items-center justify-center">
          <span className="material-symbols-outlined text-3xl text-text-faint">dns</span>
        </div>
        <h3 className="text-xl font-extrabold text-text-main mb-2">No MCP Servers</h3>
        <p className="text-sm text-text-muted max-w-[320px]">
          Add an MCP server to connect your agents with external tools and services.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border overflow-hidden shadow-sm" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="sticky top-0 z-10 shadow-[0_1px_0_0_rgba(0,0,0,0.05)]" style={{ background: 'var(--color-surface)' }}>
              <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>Server</th>
              <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>Transport</th>
              <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>Credentials</th>
              <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>Connection</th>
              <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest text-right" style={{ color: 'var(--color-text-faint)' }}>Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: 'var(--color-border-light)' }}>
            {servers.map((server) => {
              const tb = typeBranding[server.type] || typeBranding.stdio;
              const test = testingStatus[server.name];
              const isExpanded = expandedServer === server.name;

              return (
                <React.Fragment key={server.name}>
                  <tr className="hover:bg-slate-50/80 transition-all duration-200 group">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl ${tb.bg} flex items-center justify-center shadow-sm ring-4 ring-white transition-transform group-hover:scale-110`}>
                          <span className={`material-symbols-outlined text-lg ${tb.text}`}>{tb.icon}</span>
                        </div>
                        <div>
                          <div className="text-sm font-extrabold capitalize" style={{ color: 'var(--color-text-main)' }}>{server.name}</div>
                          {server.builtin && (
                            <span className="text-[9px] font-black uppercase tracking-widest text-primary">Built-in</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider ${tb.bg} ${tb.text}`}>
                        <span className={`material-symbols-outlined text-xs ${tb.text}`}>{tb.icon}</span>
                        {server.type}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => setExpandedServer(isExpanded ? null : server.name)}
                        className="flex items-center gap-2 group/cred hover:bg-slate-50 px-2 py-1 -mx-2 rounded-lg transition-colors"
                      >
                        {server.credential_status === 'ok' ? (
                          <>
                            <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/30" />
                            <span className="text-xs font-bold text-emerald-700">Ready</span>
                          </>
                        ) : (
                          <>
                            <span className="w-2 h-2 rounded-full bg-red-500 shadow-sm shadow-red-500/30" />
                            <span className="text-xs font-bold text-red-600">{server.missing_keys.length} missing</span>
                          </>
                        )}
                        <span className={`material-symbols-outlined text-sm text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
                          expand_more
                        </span>
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      {test ? (
                        <div className="flex items-center gap-2">
                          {test.status === 'testing' ? (
                            <span className="material-symbols-outlined text-base text-slate-400 animate-spin">sync</span>
                          ) : test.status === 'success' ? (
                            <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/30" />
                          ) : (
                            <span className="w-2 h-2 rounded-full bg-red-500 shadow-sm shadow-red-500/30" />
                          )}
                          <span className={`text-xs font-semibold max-w-[180px] truncate ${
                            test.status === 'success' ? 'text-emerald-700' : test.status === 'error' ? 'text-red-600' : 'text-slate-500'
                          }`} title={test.message}>
                            {test.message}
                          </span>
                        </div>
                      ) : (
                        <span className="text-[11px] font-medium text-slate-400 italic">Not tested</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => handleTest(server.name)}
                          className="p-2 hover:bg-primary/10 hover:text-primary rounded-lg transition-all"
                          title="Test Connection"
                        >
                          <span className="material-symbols-outlined text-lg">play_arrow</span>
                        </button>
                        {!server.builtin && (
                          <button
                            onClick={() => handleDelete(server.name)}
                            className="p-2 hover:bg-red-50 hover:text-red-500 rounded-lg transition-all"
                            title="Remove Server"
                          >
                            <span className="material-symbols-outlined text-lg">delete</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={5} className="px-6 py-3" style={{ background: 'var(--color-surface-hover, #f8fafc)' }}>
                        <CredentialManager serverName={server.name} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
