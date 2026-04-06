'use client';

import { useState } from 'react';
import { useConnectorInstances, useConnectorRegistry } from '@/hooks/use-connectors';
import { Connector, ConnectorInstance } from '@/types';
import ConnectorsGrid from '@/components/connectors/ConnectorsGrid';
import ConnectorSetupPanel from '@/components/connectors/ConnectorSetupPanel';

export default function ConnectorsPage() {
  const { instances = [], isLoading: instancesLoading } = useConnectorInstances();
  const { registry = [], isLoading: registryLoading } = useConnectorRegistry();
  
  const [editingInstance, setEditingInstance] = useState<ConnectorInstance | undefined>(undefined);
  const [selectedConnector, setSelectedConnector] = useState<Connector | undefined>(undefined);
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  const handleEdit = (instance: ConnectorInstance) => {
    setEditingInstance(instance);
    const connector = registry.find(c => c.id === instance.connector_id);
    setSelectedConnector(connector);
    setIsPanelOpen(true);
  };

  const handleAdd = (connector: Connector) => {
    setEditingInstance(undefined);
    setSelectedConnector(connector);
    setIsPanelOpen(true);
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Header */}
      <div className="flex items-center justify-between mb-10 sticky top-0 z-20 backdrop-blur-md py-4 -mx-4 px-4 rounded-xl border-b border-transparent hover:border-slate-100 transition-all">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary shadow-inner ring-1 ring-primary/20">
            <span className="material-symbols-outlined text-3xl font-bold">hub</span>
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tight" style={{ color: 'var(--color-text-main)' }}>
              Connector Registry
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>
                Data Source Integrations
              </p>
              <span className="w-1 h-1 rounded-full bg-slate-300" />
              <p className="text-[11px] font-bold" style={{ color: 'var(--color-text-muted)' }}>
                {instances.length} active connections
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid View */}
      <ConnectorsGrid 
        instances={instances} 
        registry={registry}
        onEdit={handleEdit} 
        onAdd={handleAdd}
        isLoading={instancesLoading || registryLoading}
      />

      {/* Slide-over Panel */}
      <ConnectorSetupPanel 
        instance={editingInstance}
        connector={selectedConnector}
        isOpen={isPanelOpen}
        onClose={() => { 
          setIsPanelOpen(false); 
          setEditingInstance(undefined); 
          setSelectedConnector(undefined);
        }}
      />
    </div>
  );
}
