'use client';

import { useEffect } from 'react';
import { EpicNode } from '@/lib/epic-parser';
import { EpicCardPreview } from './EpicCardPreview';
import { usePlanContext } from './PlanWorkspace';

interface EpicDetailDrawerProps {
  epic: EpicNode | null;
  isOpen: boolean;
  onClose: () => void;
}

export function EpicDetailDrawer({ epic, isOpen, onClose }: EpicDetailDrawerProps) {
  const { updateParsedPlan } = usePlanContext();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!epic) return null;

  const handleDeleteEpic = () => {
    if (window.confirm(`Are you sure you want to delete ${epic.ref}? This action cannot be undone.`)) {
      updateParsedPlan((doc) => {
        const newDoc = { ...doc };
        newDoc.epics = newDoc.epics.filter(e => e.ref !== epic.ref);
        
        // Also remove from depends_on of other epics
        for (const e of newDoc.epics) {
          e.depends_on = e.depends_on.filter(ref => ref !== epic.ref);
        }
        
        return newDoc;
      });
      onClose();
    }
  };

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/20 backdrop-blur-[2px] z-[100] transition-opacity"
          onClick={onClose}
        />
      )}
      
      {/* Drawer */}
      <div 
        className={`fixed top-0 right-0 h-full w-[420px] bg-surface shadow-2xl z-[101] transform transition-transform duration-300 ease-in-out border-l border-border flex flex-col ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-surface-alt/10">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-primary uppercase tracking-wider bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
              {epic.ref}
            </span>
            <h2 className="text-sm font-bold text-text-main truncate max-w-[200px]">
              {epic.title}
            </h2>
          </div>
          <button 
            onClick={onClose}
            className="p-1 hover:bg-surface-hover rounded-md text-text-faint transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <EpicCardPreview epic={epic} />
          
          {/* Delete EPIC button */}
          <div className="mt-8 pt-6 border-t border-border">
            <button
              onClick={handleDeleteEpic}
              className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-md border border-red-200 text-red-600 bg-red-50 hover:bg-red-100 transition-colors text-xs font-bold uppercase tracking-wider"
            >
              <span className="material-symbols-outlined text-[16px]">delete</span>
              Delete EPIC
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
