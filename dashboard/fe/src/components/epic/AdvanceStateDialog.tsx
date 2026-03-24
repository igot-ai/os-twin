'use client';

import React from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import { DoDItem } from '@/types';

interface AdvanceStateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  currentState: string;
  targetState: string;
  definitionOfDone: DoDItem[];
}

export default function AdvanceStateDialog({
  isOpen,
  onClose,
  onConfirm,
  currentState,
  targetState,
  definitionOfDone,
}: AdvanceStateDialogProps) {
  const uncompletedDoD = definitionOfDone.filter(item => !item.verified);
  const isBlocked = uncompletedDoD.length > 0;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Advance Epic State">
      <div className="space-y-6 p-1">
        {/* State Transition Info */}
        <div className="flex items-center justify-center gap-6 py-4 bg-surface-hover/30 rounded-lg border border-border">
          <div className="text-center">
            <span className="text-[10px] font-bold text-text-faint uppercase block mb-1">Current State</span>
            <div className="px-3 py-1 bg-surface border border-border rounded text-xs font-bold text-text-main shadow-sm">
              {currentState.toUpperCase().replace('-', ' ')}
            </div>
          </div>
          <span className="material-symbols-outlined text-text-faint" aria-hidden="true">arrow_forward</span>
          <div className="text-center">
            <span className="text-[10px] font-bold text-primary uppercase block mb-1">Target State</span>
            <div className="px-3 py-1 bg-primary-muted border border-primary/20 rounded text-xs font-bold text-primary shadow-sm">
              {targetState.toUpperCase().replace('-', ' ')}
            </div>
          </div>
        </div>

        {/* DoD Validation */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold text-text-main flex items-center gap-2">
            <span className={`material-symbols-outlined text-sm ${isBlocked ? 'text-warning' : 'text-success'}`} aria-hidden="true">
              {isBlocked ? 'warning' : 'check_circle'}
            </span>
            Definition of Done Status
          </h3>
          
          <div className="space-y-2 max-h-48 overflow-y-auto pr-1 custom-scrollbar">
            {definitionOfDone.map((item) => (
              <div 
                key={item.id} 
                className={`flex items-start gap-3 p-2.5 rounded text-xs border transition-colors ${
                  item.verified 
                    ? 'bg-success-light border-success/20 text-success-text' 
                    : 'bg-warning-light border-warning/20 text-warning-text'
                }`}
              >
                <span className="material-symbols-outlined text-sm mt-0.5" aria-hidden="true">
                  {item.verified ? 'check_box' : 'check_box_outline_blank'}
                </span>
                <span className="flex-1 font-medium">{item.text}</span>
              </div>
            ))}
          </div>

          {isBlocked && (
            <div className="p-3 bg-danger-light border border-danger/20 rounded text-[11px] text-danger-text font-medium flex gap-2 items-center animate-pulse">
              <span className="material-symbols-outlined text-sm" aria-hidden="true">block</span>
              Cannot advance state until all DoD items are completed.
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={onConfirm}
            disabled={isBlocked}
          >
            Advance to {targetState.toUpperCase().replace('-', ' ')}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
