'use client';

import React from 'react';
import { DoDItem, ACItem } from '@/types';

interface QAPanelProps {
  definitionOfDone: DoDItem[];
  acceptanceCriteria: ACItem[];
}

export default function QAPanel({ definitionOfDone, acceptanceCriteria }: QAPanelProps) {
  const verifiedCount = definitionOfDone.filter(item => item.verified).length;
  const totalCount = definitionOfDone.length;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* QA Header */}
      <div className="p-4 border-b border-border bg-surface-hover/30 shrink-0">
        <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-sm" aria-hidden="true">verified</span> Quality Assurance
        </h2>
      </div>

      {/* QA Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-6">
        {/* Definition of Done */}
        <div>
          <h3 className="text-[11px] font-bold text-text-main mb-3 flex items-center justify-between">
            Definition of Done
            <span className="text-[9px] text-success font-normal">
              {verifiedCount}/{totalCount} Verified
            </span>
          </h3>
          <div className="space-y-2">
            {definitionOfDone.map((item) => (
              <label key={item.id} className="flex items-start gap-2.5 cursor-pointer group">
                <input 
                  type="checkbox" 
                  checked={item.verified} 
                  readOnly
                  className={`mt-0.5 rounded border-border w-3.5 h-3.5 ${
                    item.verified ? 'text-success focus:ring-success' : 'text-primary focus:ring-primary'
                  }`}
                  aria-label={`Mark as ${item.verified ? 'unverified' : 'verified'}`}
                />
                <div className="flex-1 min-w-0">
                  <p className={`text-xs leading-tight ${item.verified ? 'text-text-muted' : 'text-text-main'}`}>
                    {item.text}
                  </p>
                  {item.verified && (
                    <p className="text-[9px] text-text-faint mt-0.5">
                      Verified by {item.verified_by || 'QA'} • {item.verified_at ? new Date(item.verified_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '10:45 AM'}
                    </p>
                  )}
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Acceptance Criteria */}
        <div className="pt-4 border-t border-border">
          <h3 className="text-[11px] font-bold text-text-main mb-3">Acceptance Criteria</h3>
          <div className="space-y-3">
            {acceptanceCriteria.map((item) => (
              <div 
                key={item.id} 
                className={`p-2 bg-surface-hover/30 border-l-2 rounded-r ${
                  item.status === 'pass' ? 'border-success' : 'border-primary'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-[9px] font-mono font-bold uppercase ${
                    item.status === 'pass' ? 'text-success' : 'text-primary'
                  }`}>
                    {item.status === 'pass' ? 'Passed' : 'Pending'}
                  </span>
                  <span className={`material-symbols-outlined text-xs ${
                    item.status === 'pass' ? 'text-success' : 'text-text-faint'
                  }`} aria-hidden="true">
                    {item.status === 'pass' ? 'check_circle' : 'hourglass_empty'}
                  </span>
                </div>
                <p className="text-[11px] text-text-muted italic">&quot;{item.text}&quot;</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
