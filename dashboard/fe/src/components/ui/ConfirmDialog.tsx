'use client';

import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Button } from './Button';

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isLoading?: boolean;
}

export default function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  isLoading = false,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    document.body.style.overflow = 'hidden';
    // Auto-focus cancel for safety
    cancelRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'auto';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const dialog = (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); onClose(); }}
    >
      <div
        className="w-full max-w-sm bg-surface rounded-xl shadow-modal animate-in zoom-in-95 duration-200 border border-border"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
      >
        <div className="p-5">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-9 h-9 rounded-full bg-red-500/10 flex items-center justify-center">
              <span className="material-symbols-outlined text-red-500" style={{ fontSize: 20 }}>
                warning
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-bold text-text-main mb-1">{title}</h3>
              <p className="text-xs text-text-muted leading-relaxed">{message}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 px-5 pb-4">
          <Button
            ref={cancelRef}
            variant="outline"
            size="sm"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onClose(); }}
            disabled={isLoading}
          >
            {cancelLabel}
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onConfirm(); }}
            isLoading={isLoading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );

  return createPortal(dialog, document.body);
}
