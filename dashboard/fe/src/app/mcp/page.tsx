'use client';

import { useState } from 'react';
import { McpServersTable } from '@/components/mcp/McpServersTable';
import { AddServerDialog } from '@/components/mcp/AddServerDialog';
import MemoryPoolPanel from '@/components/mcp/MemoryPoolPanel';

export default function McpPage() {
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-10 fade-in-up duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-2 border-b border-slate-100">
        <div className="space-y-1.5">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-blue-50 text-blue-600 text-[10px] font-bold uppercase tracking-widest border border-blue-100 mb-2">
            <span className="material-symbols-outlined text-xs">terminal</span>
            Tool Connectivity
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">MCP Management</h1>
          <p className="text-slate-500 text-sm font-medium">
            Manage Model Context Protocol servers, credentials, and connectivity for your AI agents.
          </p>
        </div>
        <button
          onClick={() => setIsAddDialogOpen(true)}
          className="flex items-center gap-2.5 px-6 py-3 bg-slate-900 hover:bg-slate-800 text-white text-sm font-bold rounded-2xl shadow-xl shadow-slate-900/10 transition-all transform active:scale-95 group"
        >
          <span className="material-symbols-outlined text-xl group-hover:rotate-90 transition-transform duration-300">add</span>
          Add MCP Server
        </button>
      </div>

      {/* MCP Servers Table */}
      <McpServersTable />

      {/* Memory Pool Monitor */}
      <MemoryPoolPanel />

      {/* Dialogs */}
      <AddServerDialog
        isOpen={isAddDialogOpen}
        onClose={() => setIsAddDialogOpen(false)}
      />
    </div>
  );
}
