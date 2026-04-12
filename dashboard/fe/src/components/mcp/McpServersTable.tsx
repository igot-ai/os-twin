import { Fragment, useState } from 'react';
import { useMcpServers, TestAllResult } from '@/hooks/use-mcp';
import { CredentialManager } from './CredentialManager';

const typeBranding: Record<string, { bg: string; text: string; icon: string }> = {
  local: { bg: 'bg-amber-50', text: 'text-amber-700', icon: 'terminal' },
  remote: { bg: 'bg-violet-50', text: 'text-violet-700', icon: 'cloud' },
  // Legacy aliases
  stdio: { bg: 'bg-amber-50', text: 'text-amber-700', icon: 'terminal' },
  http: { bg: 'bg-violet-50', text: 'text-violet-700', icon: 'cloud' },
};

export const McpServersTable: React.FC = () => {
  const { servers, isLoading, isError, removeServer, testServer, testAllServers, refresh } = useMcpServers();
  const [testingStatus, setTestingStatus] = useState<Record<string, { status: string; message: string }>>({});
  const [expandedServer, setExpandedServer] = useState<string | null>(null);
  const [isTestingAll, setIsTestingAll] = useState(false);
  const [testAllResults, setTestAllResults] = useState<TestAllResult | null>(null);
  const [testAllError, setTestAllError] = useState<string | null>(null);

  const handleTest = async (name: string) => {
    setTestingStatus(prev => ({ ...prev, [name]: { status: 'testing', message: 'Testing...' } }));
    try {
      const res = await testServer(name);
      setTestingStatus(prev => ({ ...prev, [name]: { status: res.status, message: res.message } }));
    } catch (e) {
      setTestingStatus(prev => ({ ...prev, [name]: { status: 'error', message: 'Failed to test' } }));
    }
  };

  const handleTestAll = async () => {
    setIsTestingAll(true);
    setTestAllError(null);
    setTestAllResults(null);

    // Set all servers to "testing" status
    const testingMap: Record<string, { status: string; message: string }> = {};
    for (const server of servers || []) {
      testingMap[server.name] = { status: 'testing', message: 'Testing via opencode...' };
    }
    setTestingStatus(testingMap);

    try {
      const results = await testAllServers();

      if (results.error) {
        setTestAllError(results.error);
        setTestingStatus({});
      } else {
        // Map test-all results to per-server testingStatus
        const statusMap: Record<string, { status: string; message: string }> = {};
        for (const server of results.servers) {
          statusMap[server.name] = {
            status: server.status === 'connected' ? 'success' : 'error',
            message: server.message || (server.status === 'connected' ? 'Connected' : 'Failed'),
          };
        }
        setTestingStatus(statusMap);
        setTestAllResults(results);
      }
    } catch (e) {
      setTestAllError('Failed to run test. Is the opencode CLI installed?');
      setTestingStatus({});
    } finally {
      setIsTestingAll(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (confirm(`Are you sure you want to remove ${name}?`)) {
      await removeServer(name);
      // Also remove from test results if present
      if (testAllResults) {
        setTestAllResults({
          ...testAllResults,
          servers: testAllResults.servers.filter(s => s.name !== name),
          total: testAllResults.total - 1,
          failed: testAllResults.failed - 1,
        });
      }
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

  // Check which servers failed in test-all (for prominent delete)
  const failedServerNames = new Set(
    testAllResults?.servers.filter(s => s.status === 'failed').map(s => s.name) ?? []
  );

  return (
    <div className="rounded-2xl border overflow-hidden shadow-sm" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
      {/* ── Toolbar ── */}
      <div className="px-6 py-3 flex items-center justify-between border-b" style={{ borderColor: 'var(--color-border-light)' }}>
        <div className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>
          {servers.length} server{servers.length !== 1 ? 's' : ''}
        </div>
        <button
          onClick={handleTestAll}
          disabled={isTestingAll}
          className="flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-xl transition-all border-2 border-slate-200 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          title="Compile config and run opencode mcp list to test all servers"
        >
          <span className={`material-symbols-outlined text-base ${isTestingAll ? 'animate-spin' : ''}`}>
            {isTestingAll ? 'sync' : 'network_check'}
          </span>
          {isTestingAll ? 'Testing All...' : 'Test All Servers'}
        </button>
      </div>

      {/* ── Test All Error Banner ── */}
      {testAllError && (
        <div className="px-6 py-3 bg-red-50 border-b border-red-100 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-red-700">
            <span className="material-symbols-outlined text-base">error</span>
            <span className="font-semibold">{testAllError}</span>
          </div>
          <button
            onClick={() => setTestAllError(null)}
            className="text-red-400 hover:text-red-600 transition-colors p-1 rounded-lg hover:bg-red-100"
          >
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>
      )}

      {/* ── Test All Results Summary ── */}
      {testAllResults && !testAllError && (
        <div className="px-6 py-3 border-b flex items-center justify-between" style={{ background: testAllResults.failed > 0 ? '#fef2f2' : '#f0fdf4', borderColor: 'var(--color-border-light)' }}>
          <div className="flex items-center gap-5 text-sm">
            <span className="font-extrabold" style={{ color: 'var(--color-text-main)' }}>
              {testAllResults.total} tested
            </span>
            <span className="flex items-center gap-1.5 font-bold text-emerald-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/30" />
              {testAllResults.connected} connected
            </span>
            {testAllResults.failed > 0 && (
              <span className="flex items-center gap-1.5 font-bold text-red-600">
                <span className="w-2 h-2 rounded-full bg-red-500 shadow-sm shadow-red-500/30" />
                {testAllResults.failed} failed
              </span>
            )}
          </div>
          <button
            onClick={() => { setTestAllResults(null); setTestingStatus({}); }}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 rounded-lg hover:bg-white/60"
          >
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>
      )}

      {/* ── Table ── */}
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
              const tb = typeBranding[server.type] || typeBranding.local;
              const test = testingStatus[server.name];
              const isExpanded = expandedServer === server.name;
              const isFailed = failedServerNames.has(server.name);

              return (
                <Fragment key={server.name}>
                  <tr className={`transition-all duration-200 group ${isFailed ? 'bg-red-50/40' : 'hover:bg-slate-50/80'}`}>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl ${isFailed ? 'bg-red-50 ring-red-100' : tb.bg} flex items-center justify-center shadow-sm ring-4 ring-white transition-transform group-hover:scale-110`}>
                          <span className={`material-symbols-outlined text-lg ${isFailed ? 'text-red-500' : tb.text}`}>
                            {isFailed ? 'error' : tb.icon}
                          </span>
                        </div>
                        <div>
                          <div className="text-sm font-extrabold capitalize" style={{ color: 'var(--color-text-main)' }}>{server.name}</div>
                          <div className="flex items-center gap-2">
                            {server.builtin && (
                              <span className="text-[9px] font-black uppercase tracking-widest text-primary">Built-in</span>
                            )}
                            {isFailed && (
                              <span className="text-[9px] font-black uppercase tracking-widest text-red-500">Failed</span>
                            )}
                          </div>
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
                          <span className={`text-xs font-semibold max-w-[240px] truncate ${
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
                      <div className={`flex items-center justify-end gap-1 transition-opacity ${
                        isFailed ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                      }`}>
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
                            className={`p-2 rounded-lg transition-all ${
                              isFailed
                                ? 'bg-red-100 text-red-600 hover:bg-red-200'
                                : 'hover:bg-red-50 hover:text-red-500'
                            }`}
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
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
