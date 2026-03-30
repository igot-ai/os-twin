import React, { useState } from 'react';
import { useMcpCredentials } from '@/hooks/use-mcp';

interface CredentialManagerProps {
  serverName: string;
}

export const CredentialManager: React.FC<CredentialManagerProps> = ({ serverName }) => {
  const { credentials, isLoading, isError, setCredential, deleteCredential, refresh } = useMcpCredentials(serverName);
  const [editingKey, setEditingKey] = useState<{ vault_server: string; key: string } | null>(null);
  const [newValue, setNewValue] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);

  const handleUpdate = async () => {
    if (!editingKey) return;
    setIsUpdating(true);
    try {
      await setCredential(editingKey.vault_server, editingKey.key, newValue);
      setEditingKey(null);
      setNewValue('');
      refresh();
    } catch (e) {
      alert('Failed to update credential');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async (vault_server: string, key: string) => {
    if (confirm(`Delete credential for ${key}?`)) {
      await deleteCredential(vault_server, key);
      refresh();
    }
  };

  if (isLoading) return <div className="text-[10px] text-slate-400 italic px-4 py-2">Loading credentials...</div>;
  if (isError) return <div className="text-[10px] text-red-500 italic px-4 py-2">Failed to load credentials</div>;
  if (!credentials || credentials.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 p-2 border border-slate-200 rounded-md bg-white">
      <div className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-1.5 px-2">
        <span className="material-symbols-outlined text-[12px]">vpn_key</span>
        Required Credentials
      </div>
      <div className="space-y-1">
        {credentials.map((cred) => (
          <div key={`${cred.vault_server}/${cred.key}`} className="flex items-center justify-between gap-3 px-3 py-1.5 rounded-md hover:bg-slate-50 transition-colors group">
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-slate-700">{cred.key}</span>
              <span className="text-[9px] text-slate-400 font-mono tracking-tighter opacity-0 group-hover:opacity-100 transition-opacity">
                {cred.vault_server}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              {editingKey?.key === cred.key && editingKey?.vault_server === cred.vault_server ? (
                <div className="flex items-center gap-1.5 animate-in fade-in slide-in-from-right-1 duration-200">
                  <input
                    type="password"
                    placeholder="New value..."
                    className="text-[11px] px-2 py-1 border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                    value={newValue}
                    onChange={(e) => setNewValue(e.target.value)}
                    autoFocus
                  />
                  <button
                    onClick={handleUpdate}
                    disabled={isUpdating}
                    className="p-1 text-green-600 hover:bg-green-50 rounded-md disabled:opacity-50 transition-colors"
                  >
                    <span className="material-symbols-outlined text-base">check</span>
                  </button>
                  <button
                    onClick={() => { setEditingKey(null); setNewValue(''); }}
                    className="p-1 text-slate-400 hover:bg-slate-50 rounded-md transition-colors"
                  >
                    <span className="material-symbols-outlined text-base">close</span>
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setEditingKey({ vault_server: cred.vault_server, key: cred.key })}
                    className="px-2 py-0.5 text-[10px] font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded transition-colors"
                  >
                    Update
                  </button>
                  <button
                    onClick={() => handleDelete(cred.vault_server, cred.key)}
                    className="px-2 py-0.5 text-[10px] font-semibold text-red-600 bg-red-50 hover:bg-red-100 rounded transition-colors"
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
