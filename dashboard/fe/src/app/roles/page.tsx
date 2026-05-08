'use client';

import { useState } from 'react';
import { useRoles } from '@/hooks/use-roles';
import { useSkills } from '@/hooks/use-skills';
import { useMcpServers } from '@/hooks/use-mcp';
import { Role } from '@/types';
import RolesTable from '@/components/roles/RolesTable';
import RoleEditorPanel from '@/components/roles/RoleEditorPanel';

export default function RolesPage() {
  const { roles = [], isLoading: rolesLoading } = useRoles();
  const { skills = [] } = useSkills();
  const { servers: mcpServers = [] } = useMcpServers();
  
  const [editingRole, setEditingRole] = useState<Role | undefined>(undefined);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const filteredRoles = roles.filter(role => 
    role.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    role.version.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleEdit = (role: Role) => {
    setEditingRole(role);
    setIsPanelOpen(true);
  };

  const handleAdd = () => {
    setEditingRole(undefined);
    setIsPanelOpen(true);
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Header */}
      <div className="flex items-center justify-between mb-10 sticky top-0 z-20 backdrop-blur-md py-4 -mx-4 px-4 rounded-xl border-b border-transparent hover:border-slate-100 transition-all">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary shadow-inner ring-1 ring-primary/20">
            <span className="material-symbols-outlined text-3xl font-bold">badge</span>
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tight" style={{ color: 'var(--color-text-main)' }}>
              Role Matrix
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>
                System Orchestrator
              </p>
              <span className="w-1 h-1 rounded-full bg-slate-300" />
              <p className="text-[11px] font-bold" style={{ color: 'var(--color-text-muted)' }}>
                {roles.length} active agent templates {searchQuery && `(${filteredRoles.length} matching)`}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="relative group">
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-primary transition-colors">
              search
            </span>
            <input
              type="text"
              placeholder="Search roles..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-11 pr-4 py-2.5 w-64 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-sm"
              style={{ color: 'var(--color-text-main)' }}
            />
          </div>
          
          <button 
            onClick={handleAdd}
            className="flex items-center gap-2.5 px-6 py-3 rounded-xl text-white text-sm font-extrabold shadow-xl shadow-primary/25 hover:brightness-105 active:scale-[0.98] transition-all"
            style={{ background: 'var(--color-primary)' }}
          >
            <span className="material-symbols-outlined text-xl">add_moderator</span>
            Provision New Role
          </button>
        </div>
      </div>

      {/* Main Table View */}
      <RolesTable 
        roles={filteredRoles} 
        skills={skills}
        mcpServers={mcpServers}
        onEdit={handleEdit} 
        onAdd={handleAdd}
        isLoading={rolesLoading}
        totalRoles={roles.length}
      />

      {/* Bottom Drawer */}
      <RoleEditorPanel 
        role={editingRole}
        isOpen={isPanelOpen}
        onClose={() => { setIsPanelOpen(false); setEditingRole(undefined); }}
        existingRoles={roles}
      />
    </div>
  );
}
