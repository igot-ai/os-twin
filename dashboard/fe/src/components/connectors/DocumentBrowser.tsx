'use client';

import { useConnectorDocuments } from '@/hooks/use-connectors';

interface DocumentBrowserProps {
  isOpen: boolean;
  onClose: () => void;
  instanceId: string;
  connectorName: string;
}

export default function DocumentBrowser({ isOpen, onClose, instanceId, connectorName }: DocumentBrowserProps) {
  const { documents = [], isLoading, isError, refresh } = useConnectorDocuments(isOpen ? instanceId : null);

  if (!isOpen) return null;

  return (
    <div className="absolute inset-0 z-[60] bg-white flex flex-col animate-in slide-in-from-right duration-500 shadow-2xl">
      <div className="p-6 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white/80 backdrop-blur-md z-10">
        <div className="flex items-center gap-4">
          <button 
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-full text-slate-400 hover:text-slate-900 transition-colors"
          >
            <span className="material-symbols-outlined font-bold">arrow_back</span>
          </button>
          <div>
            <h2 className="text-xl font-black text-slate-900 leading-tight">Document Browser</h2>
            <p className="text-[10px] font-black text-primary uppercase tracking-widest">{connectorName} Index</p>
          </div>
        </div>
        <button 
          onClick={() => refresh()}
          disabled={isLoading}
          className="p-2 hover:bg-slate-100 rounded-full text-slate-400 hover:text-slate-900 transition-colors disabled:opacity-50"
        >
          <span className={`material-symbols-outlined font-bold ${isLoading ? 'animate-spin' : ''}`}>sync</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-50/50">
        {isLoading && (
          <div className="p-8 space-y-4">
             {[1, 2, 3, 4, 5].map(i => (
               <div key={i} className="h-32 bg-white rounded-2xl border border-slate-100 animate-pulse" />
             ))}
          </div>
        )}

        {isError && (
          <div className="p-12 text-center space-y-4">
            <span className="material-symbols-outlined text-red-400 text-5xl">cloud_off</span>
            <p className="text-slate-500 font-bold">Failed to load documents</p>
            <button 
              onClick={() => refresh()}
              className="px-4 py-2 bg-primary/10 text-primary font-bold rounded-xl hover:bg-primary/20 transition-all text-xs"
            >
              Retry
            </button>
          </div>
        )}

        {!isLoading && documents.length === 0 && !isError && (
          <div className="p-20 text-center space-y-6">
            <div className="w-24 h-24 rounded-full bg-slate-100 flex items-center justify-center text-slate-300 mx-auto">
              <span className="material-symbols-outlined text-5xl">folder_zip</span>
            </div>
            <div className="max-w-xs mx-auto">
              <h3 className="text-lg font-black text-slate-900 mb-2">No Documents Yet</h3>
              <p className="text-sm text-slate-500 leading-relaxed">
                We haven&apos;t indexed any content from this {connectorName} connection. Try testing the connection or checking your sync settings.
              </p>
            </div>
          </div>
        )}

        {documents.length > 0 && (
          <div className="p-6 grid grid-cols-1 gap-4">
            {documents.map((doc) => (
              <div 
                key={doc.externalId}
                className="p-5 bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md hover:border-primary/20 transition-all group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <h4 className="font-bold text-slate-900 group-hover:text-primary transition-colors leading-tight mb-2">
                      {doc.title || 'Untitled Document'}
                    </h4>
                    <div className="flex items-center gap-3 text-[11px] font-bold text-slate-400 uppercase tracking-tight">
                      <span className="flex items-center gap-1 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">
                        <span className="material-symbols-outlined text-[14px]">id_card</span>
                        {doc.externalId.substring(0, 12)}...
                      </span>
                      {doc.mimeType && (
                         <span className="flex items-center gap-1 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">
                           <span className="material-symbols-outlined text-[14px]">description</span>
                           {doc.mimeType}
                         </span>
                      )}
                    </div>
                  </div>
                  {doc.sourceUrl && (
                    <a 
                      href={doc.sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 bg-slate-50 rounded-xl text-slate-400 hover:text-primary hover:bg-primary/5 transition-all"
                    >
                      <span className="material-symbols-outlined text-xl">open_in_new</span>
                    </a>
                  )}
                </div>
                {doc.content && (
                   <p className="text-[11px] text-slate-500 mt-4 line-clamp-3 font-mono bg-slate-50/50 p-3 rounded-xl border border-slate-100/50 italic leading-relaxed">
                     {doc.content.substring(0, 300)}...
                   </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
