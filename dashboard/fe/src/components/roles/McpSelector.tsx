'use client';

import { useState, useRef, useEffect } from 'react';
import { useMcpServers } from '@/hooks/use-mcp';

interface McpSelectorProps {
  selectedMcpRefs: string[];
  onChange: (mcpRefs: string[]) => void;
}

export default function McpSelector({ selectedMcpRefs, onChange }: McpSelectorProps) {
  const { servers: allServers, isLoading } = useMcpServers();
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const servers = allServers || [];

  const selectedServers = servers.filter(s => selectedMcpRefs.includes(s.name));
  const availableServers = servers.filter(s =>
    !selectedMcpRefs.includes(s.name) &&
    s.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const addServer = (name: string) => {
    onChange([...selectedMcpRefs, name]);
    setSearchTerm('');
    setIsOpen(false);
  };

  const removeServer = (name: string) => {
    onChange(selectedMcpRefs.filter(ref => ref !== name));
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <div
        className="flex flex-wrap gap-2 p-2 min-h-[44px] rounded-lg border transition-all cursor-text focus-within:ring-2 focus-within:ring-primary/20"
        style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
        onClick={() => setIsOpen(true)}
      >
        {selectedServers.map(server => (
          <span
            key={server.name}
            className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold animate-in zoom-in-95"
            style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}
          >
            <span className="px-1 py-0.5 rounded text-[9px] font-black uppercase bg-slate-200 text-slate-600">
              {server.type}
            </span>
            {server.name}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); removeServer(server.name); }}
              className="hover:opacity-70"
            >
              <span className="material-symbols-outlined text-[10px] leading-none">close</span>
            </button>
          </span>
        ))}
        {/* Chips for selected refs that aren't in current server list */}
        {selectedMcpRefs
          .filter(ref => !servers.some(s => s.name === ref))
          .map(ref => (
            <span
              key={ref}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold bg-slate-100 text-slate-500"
            >
              {ref}
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); removeServer(ref); }}
                className="hover:opacity-70"
              >
                <span className="material-symbols-outlined text-[10px] leading-none">close</span>
              </button>
            </span>
          ))}
        <input
          type="text"
          className="flex-1 bg-transparent border-none outline-none text-xs min-w-[120px]"
          placeholder={selectedMcpRefs.length === 0 ? 'Search MCP servers...' : ''}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onFocus={() => setIsOpen(true)}
        />
      </div>

      {isOpen && (
        <div
          className="absolute z-50 mt-2 w-full max-h-60 overflow-auto rounded-xl border shadow-xl fade-in slide-in-from-top-2"
          style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
        >
          {isLoading ? (
            <div className="p-4 text-center text-xs text-text-muted">Loading MCP servers...</div>
          ) : availableServers.length === 0 ? (
            <div className="p-4 text-center text-xs text-text-muted">No matching MCP servers found</div>
          ) : (
            <div className="p-1">
              {availableServers.map(server => (
                <button
                  key={server.name}
                  type="button"
                  className="w-full text-left p-3 rounded-lg hover:bg-slate-50 transition-colors group"
                  onClick={() => addServer(server.name)}
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold group-hover:text-primary transition-colors">
                        {server.name}
                      </span>
                      {server.builtin && (
                        <span className="px-1 py-0.5 rounded text-[9px] font-bold bg-indigo-100 text-indigo-600 uppercase">
                          builtin
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 uppercase">
                      {server.type}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${server.status === 'active' ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                    <span className="text-[11px] text-text-muted">{server.status}</span>
                    {server.credential_status === 'missing' && (
                      <span className="text-[10px] font-bold text-amber-600 flex items-center gap-0.5">
                        <span className="material-symbols-outlined text-xs">warning</span>
                        Missing key: {server.missing_keys.join(', ')}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
