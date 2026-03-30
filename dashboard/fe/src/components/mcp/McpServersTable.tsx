import React, { useState } from 'react';
import { useMcpServers, McpServer } from '@/hooks/use-mcp';
import { CredentialManager } from './CredentialManager';

export const McpServersTable: React.FC = () => {
  const { servers, isLoading, isError, removeServer, testServer, refresh } = useMcpServers();
  const [testingStatus, setTestingStatus] = useState<Record<string, { status: string; message: string }>>({});

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

  if (isLoading) return <div className="p-8">Loading MCP servers...</div>;
  if (isError) return <div className="p-8 text-red-500">Failed to load MCP servers</div>;
  if (!servers || servers.length === 0) return <div className="p-8 text-slate-500">No MCP servers installed.</div>;

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Server Name</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Type</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Credentials</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Test Result</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-200">
          {servers.map((server) => (
            <React.Fragment key={server.name}>
              <tr className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-4 whitespace-nowrap">
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-slate-900">{server.name}</span>
                    {server.builtin && <span className="text-[10px] text-blue-500 font-semibold">BUILT-IN</span>}
                  </div>
                </td>
                <td className="px-4 py-4 whitespace-nowrap">
                  <span className={`px-2 py-1 text-[10px] font-bold rounded-full uppercase ${
                    server.type === 'http' ? 'bg-purple-100 text-purple-700' : 'bg-orange-100 text-orange-700'
                  }`}>
                    {server.type}
                  </span>
                </td>
                <td className="px-4 py-4">
                  <div className="flex items-center gap-1.5">
                    {server.credential_status === 'ok' ? (
                      <span className="text-green-600 text-lg material-symbols-outlined">check_circle</span>
                    ) : (
                      <span className="text-red-500 text-lg material-symbols-outlined">error</span>
                    )}
                    <span className={`text-xs ${server.credential_status === 'ok' ? 'text-green-700' : 'text-red-700'}`}>
                      {server.credential_status === 'ok' ? 'Ready' : `${server.missing_keys.length} missing`}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-4 whitespace-nowrap">
                  {testingStatus[server.name] ? (
                    <div className="flex items-center gap-2">
                      {testingStatus[server.name].status === 'testing' ? (
                        <span className="animate-spin material-symbols-outlined text-base text-slate-400">sync</span>
                      ) : testingStatus[server.name].status === 'success' ? (
                        <span className="text-green-600 material-symbols-outlined text-base">check</span>
                      ) : (
                        <span className="text-red-500 material-symbols-outlined text-base">close</span>
                      )}
                      <span className="text-xs text-slate-600 max-w-[150px] truncate" title={testingStatus[server.name].message}>
                        {testingStatus[server.name].message}
                      </span>
                    </div>
                  ) : (
                    <span className="text-[10px] text-slate-400 italic">Not tested yet</span>
                  )}
                </td>
                <td className="px-4 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => handleTest(server.name)}
                      className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                      title="Test Connection"
                    >
                      <span className="material-symbols-outlined text-lg">play_arrow</span>
                    </button>
                    {!server.builtin && (
                      <button
                        onClick={() => handleDelete(server.name)}
                        className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                        title="Remove Server"
                      >
                        <span className="material-symbols-outlined text-lg">delete</span>
                      </button>
                    )}
                  </div>
                </td>
              </tr>
              <tr className="bg-slate-50/30">
                <td colSpan={5} className="px-4 py-2">
                  <CredentialManager serverName={server.name} />
                </td>
              </tr>
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
};
