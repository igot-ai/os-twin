'use client';

import { Connector, ConnectorInstance } from '@/types';
import ConnectorCard from './ConnectorCard';
import RegistryCard from './RegistryCard';

interface ConnectorsGridProps {
  instances: ConnectorInstance[];
  registry: Connector[];
  onEdit: (instance: ConnectorInstance) => void;
  onAdd: (connector: Connector) => void;
  isLoading?: boolean;
}

export default function ConnectorsGrid({ 
  instances, 
  registry, 
  onEdit, 
  onAdd, 
  isLoading 
}: ConnectorsGridProps) {
  
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
          <div key={i} className="h-56 rounded-2xl bg-slate-100 animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-16">
      {/* Active Instances */}
      {instances.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              Configured Instances
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {instances.map(instance => (
              <ConnectorCard 
                key={instance.id} 
                instance={instance} 
                connector={registry.find(c => c.id === instance.connector_id)}
                onClick={() => onEdit(instance)}
              />
            ))}
          </div>
        </section>
      )}

      {/* Available to Add */}
      <section>
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
            Registry
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {registry.map(connector => (
            <RegistryCard 
              key={connector.id} 
              connector={connector} 
              onClick={() => onAdd(connector)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
