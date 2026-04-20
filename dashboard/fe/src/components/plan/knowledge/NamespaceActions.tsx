'use client';

import React, { useState, useCallback } from 'react';
import { useNotificationStore } from '@/lib/stores/notificationStore';
import { apiPost, apiPut } from '@/lib/api-client';

interface NamespaceActionsProps {
  namespace: string;
  onRefresh?: () => void;
}

export default function NamespaceActions({ namespace, onRefresh }: NamespaceActionsProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [showRetentionModal, setShowRetentionModal] = useState(false);
  const [retentionPolicy, setRetentionPolicy] = useState<'manual' | 'ttl_days'>('manual');
  const [ttlDays, setTtlDays] = useState(30);
  const [isBackingUp, setIsBackingUp] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSavingRetention, setIsSavingRetention] = useState(false);
  const addToast = useNotificationStore((state) => state.addToast);

  const handleBackup = useCallback(async () => {
    setIsBackingUp(true);
    setShowMenu(false);
    try {
      // The backup endpoint returns a binary stream, so we need the raw Response
      // rather than going through apiPost (which parses JSON and returns T).
      const { getApiBaseUrl } = await import('@/lib/runtime-config');
      const BASE_URL = getApiBaseUrl();
      const response = await fetch(
        `${BASE_URL}/api/knowledge/namespaces/${namespace}/backup?stream=true`,
        { method: 'POST', credentials: 'include' },
      );

      if (!response.ok) {
        throw new Error(`Backup failed: ${response.statusText}`);
      }

      // Create download link
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${namespace}.backup.tar.zst`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      addToast({
        type: 'success',
        title: 'Backup Downloaded',
        message: `Backup of "${namespace}" has been downloaded.`,
        autoDismiss: true,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Backup failed';
      addToast({
        type: 'error',
        title: 'Backup Failed',
        message,
        autoDismiss: false,
      });
    } finally {
      setIsBackingUp(false);
    }
  }, [namespace, addToast]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    setShowMenu(false);
    try {
      // apiPost<T> parses JSON and returns T directly — no .json() needed
      const data = await apiPost<{ imports_count: number }>(
        `/api/knowledge/namespaces/${namespace}/refresh`,
      );

      addToast({
        type: 'success',
        title: 'Refresh Started',
        message: `Re-importing ${data.imports_count} folder(s) into "${namespace}".`,
        autoDismiss: true,
      });

      onRefresh?.();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Refresh failed';
      addToast({
        type: 'error',
        title: 'Refresh Failed',
        message,
        autoDismiss: false,
      });
    } finally {
      setIsRefreshing(false);
    }
  }, [namespace, addToast, onRefresh]);

  const handleSaveRetention = useCallback(async () => {
    setIsSavingRetention(true);
    try {
      await apiPut(`/api/knowledge/namespaces/${namespace}/retention`, {
        policy: retentionPolicy,
        ttl_days: retentionPolicy === 'ttl_days' ? ttlDays : null,
      });
      
      addToast({
        type: 'success',
        title: 'Retention Policy Updated',
        message: `Retention for "${namespace}" set to ${retentionPolicy === 'ttl_days' ? `${ttlDays} days` : 'manual'}.`,
        autoDismiss: true,
      });
      
      setShowRetentionModal(false);
      onRefresh?.();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to update retention';
      addToast({
        type: 'error',
        title: 'Update Failed',
        message,
        autoDismiss: false,
      });
    } finally {
      setIsSavingRetention(false);
    }
  }, [namespace, retentionPolicy, ttlDays, addToast, onRefresh]);

  return (
    <>
      {/* Action menu button */}
      <div className="relative">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowMenu(!showMenu);
          }}
          className="p-1 rounded hover:bg-surface-hover transition-colors"
          aria-label="Namespace actions"
        >
          <span 
            className="material-symbols-outlined text-[18px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            more_vert
          </span>
        </button>
        
        {/* Dropdown menu */}
        {showMenu && (
          <>
            <div 
              className="fixed inset-0 z-40" 
              onClick={() => setShowMenu(false)}
            />
            <div 
              className="absolute right-0 top-full mt-1 z-50 w-48 rounded-lg border shadow-lg"
              style={{ 
                background: 'var(--color-surface)', 
                borderColor: 'var(--color-border)' 
              }}
            >
              <div className="py-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleBackup();
                  }}
                  disabled={isBackingUp}
                  className="w-full px-4 py-2 text-left text-xs flex items-center gap-2 hover:bg-surface-hover transition-colors disabled:opacity-50"
                  style={{ color: 'var(--color-text-main)' }}
                >
                  <span className="material-symbols-outlined text-[16px]">
                    {isBackingUp ? 'sync' : 'download'}
                  </span>
                  {isBackingUp ? 'Backing up...' : 'Backup'}
                </button>
                
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRefresh();
                  }}
                  disabled={isRefreshing}
                  className="w-full px-4 py-2 text-left text-xs flex items-center gap-2 hover:bg-surface-hover transition-colors disabled:opacity-50"
                  style={{ color: 'var(--color-text-main)' }}
                >
                  <span className="material-symbols-outlined text-[16px]">
                    {isRefreshing ? 'sync' : 'refresh'}
                  </span>
                  {isRefreshing ? 'Refreshing...' : 'Refresh'}
                </button>
                
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowMenu(false);
                    setShowRetentionModal(true);
                  }}
                  className="w-full px-4 py-2 text-left text-xs flex items-center gap-2 hover:bg-surface-hover transition-colors"
                  style={{ color: 'var(--color-text-main)' }}
                >
                  <span className="material-symbols-outlined text-[16px]">schedule</span>
                  Retention Policy
                </button>
              </div>
            </div>
          </>
        )}
      </div>
      
      {/* Retention Policy Modal */}
      {showRetentionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div 
            className="rounded-2xl border p-6 w-full max-w-md mx-4"
            style={{ 
              background: 'var(--color-surface)', 
              borderColor: 'var(--color-border)' 
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-main)' }}>
                Retention Policy
              </h3>
              <button
                onClick={() => setShowRetentionModal(false)}
                className="p-1 rounded hover:bg-surface-hover transition-colors"
                aria-label="Close modal"
              >
                <span className="material-symbols-outlined text-[20px]" style={{ color: 'var(--color-text-muted)' }}>
                  close
                </span>
              </button>
            </div>
            
            <p className="text-xs mb-4" style={{ color: 'var(--color-text-muted)' }}>
              Configure automatic cleanup of import records for "{namespace}".
            </p>
            
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-2" style={{ color: 'var(--color-text-muted)' }}>
                  Policy
                </label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="retention"
                      checked={retentionPolicy === 'manual'}
                      onChange={() => setRetentionPolicy('manual')}
                      className="w-4 h-4"
                    />
                    <span className="text-xs" style={{ color: 'var(--color-text-main)' }}>
                      Manual (no auto-cleanup)
                    </span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="retention"
                      checked={retentionPolicy === 'ttl_days'}
                      onChange={() => setRetentionPolicy('ttl_days')}
                      className="w-4 h-4"
                    />
                    <span className="text-xs" style={{ color: 'var(--color-text-main)' }}>
                      Auto-delete after TTL
                    </span>
                  </label>
                </div>
              </div>
              
              {retentionPolicy === 'ttl_days' && (
                <div>
                  <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--color-text-muted)' }}>
                    TTL (days)
                  </label>
                  <input
                    type="number"
                    value={ttlDays}
                    onChange={(e) => setTtlDays(parseInt(e.target.value) || 30)}
                    min={1}
                    max={3650}
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{ 
                      background: 'var(--color-background)', 
                      borderColor: 'var(--color-border)',
                      color: 'var(--color-text-main)'
                    }}
                  />
                  <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-faint)' }}>
                    Import records older than this will be automatically deleted.
                  </p>
                </div>
              )}
            </div>
            
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setShowRetentionModal(false)}
                className="px-4 py-2 rounded-lg text-xs font-medium transition-colors"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRetention}
                disabled={isSavingRetention}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {isSavingRetention ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
