'use client';

import React, { useState, useCallback } from 'react';
import { NamespaceMetaResponse } from '@/hooks/use-knowledge-namespaces';
import NamespaceActions from './NamespaceActions';

interface NamespaceListProps {
  namespaces: NamespaceMetaResponse[];
  selectedNamespace: string | null;
  onSelect: (namespace: string) => void;
  onCreate: (name: string, description?: string) => Promise<void>;
  onDelete: (namespace: string) => Promise<void>;
  isLoading: boolean;
  onNamespaceUpdated?: () => void;
}

export default function NamespaceList({
  namespaces,
  selectedNamespace,
  onSelect,
  onCreate,
  onDelete,
  isLoading,
  onNamespaceUpdated,
}: NamespaceListProps) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Namespace name validation (matches backend regex)
  const validateName = useCallback((name: string): string | null => {
    if (!name.trim()) return 'Name is required';
    if (name.length > 64) return 'Name must be 64 characters or less';
    if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(name)) {
      return 'Name must start with lowercase letter or number, and contain only lowercase letters, numbers, underscores, and hyphens';
    }
    if (namespaces.some(ns => ns.name === name)) {
      return 'A namespace with this name already exists';
    }
    return null;
  }, [namespaces]);

  const handleCreate = useCallback(async () => {
    const error = validateName(newName);
    if (error) {
      setValidationError(error);
      return;
    }

    setIsCreating(true);
    try {
      await onCreate(newName, newDescription || undefined);
      setShowCreateModal(false);
      setNewName('');
      setNewDescription('');
      setValidationError(null);
    } finally {
      setIsCreating(false);
    }
  }, [newName, newDescription, validateName, onCreate]);

  const handleDelete = useCallback(async (namespace: string) => {
    setIsDeleting(true);
    try {
      await onDelete(namespace);
      setDeleteConfirm(null);
    } finally {
      setIsDeleting(false);
    }
  }, [onDelete]);

  return (
    <div className="h-full overflow-y-auto p-4" style={{ scrollbarWidth: 'thin' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-main)' }}>
            Knowledge Namespaces
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
            {namespaces.length} namespace{namespaces.length !== 1 ? 's' : ''} available
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-primary text-white hover:bg-primary/90 transition-colors"
          aria-label="Create new namespace"
        >
          <span className="material-symbols-outlined text-[16px]">add</span>
          New
        </button>
      </div>

      {/* Namespace list */}
      <div className="space-y-2">
        {namespaces.map((ns) => (
          <div
            key={ns.name}
            className={`group rounded-xl border p-3 cursor-pointer transition-all ${
              selectedNamespace === ns.name 
                ? 'border-primary bg-primary/5' 
                : 'border-border hover:border-border/80 hover:bg-surface-hover'
            }`}
            onClick={() => onSelect(ns.name)}
            onKeyDown={(e) => e.key === 'Enter' && onSelect(ns.name)}
            tabIndex={0}
            role="button"
            aria-label={`Select namespace ${ns.name}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span 
                    className="material-symbols-outlined text-[18px]"
                    style={{ color: 'var(--color-primary)' }}
                  >
                    folder_open
                  </span>
                  <h4 className="text-sm font-medium truncate" style={{ color: 'var(--color-text-main)' }}>
                    {ns.name}
                  </h4>
                </div>
                {ns.description && (
                  <p className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>
                    {ns.description}
                  </p>
                )}
              </div>
              
              {/* Stats badges */}
              <div className="flex items-center gap-1.5 ml-2">
                {ns.stats.files_indexed > 0 && (
                  <span 
                    className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                    style={{ background: 'var(--color-surface-hover)', color: 'var(--color-text-muted)' }}
                  >
                    {ns.stats.files_indexed} files
                  </span>
                )}
                {ns.stats.chunks > 0 && (
                  <span 
                    className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                    style={{ background: 'var(--color-surface-hover)', color: 'var(--color-text-muted)' }}
                  >
                    {ns.stats.chunks} chunks
                  </span>
                )}
              </div>
            </div>

            {/* Stats row */}
            <div className="flex items-center gap-3 mt-2 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
              {ns.stats.entities > 0 && (
                <span>{ns.stats.entities} entities</span>
              )}
              {ns.stats.vectors > 0 && (
                <span>{ns.stats.vectors} vectors</span>
              )}
              <span className="ml-auto">
                {ns.language}
              </span>
            </div>

            {/* Action buttons */}
            <div className="absolute top-2 right-2 flex items-center gap-1">
              <NamespaceActions 
                namespace={ns.name} 
                onRefresh={onNamespaceUpdated}
              />
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setDeleteConfirm(ns.name);
                }}
                className="p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-danger/10"
                style={{ color: 'var(--color-danger)' }}
                aria-label={`Delete namespace ${ns.name}`}
              >
                <span className="material-symbols-outlined text-[16px]">delete</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {namespaces.length === 0 && (
        <div className="text-center py-8">
          <span 
            className="material-symbols-outlined text-[32px] mb-2"
            style={{ color: 'var(--color-text-muted)' }}
          >
            folder_off
          </span>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            No namespaces yet. Create one to get started.
          </p>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
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
                Create Namespace
              </h3>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setNewName('');
                  setNewDescription('');
                  setValidationError(null);
                }}
                className="p-1 rounded hover:bg-surface-hover transition-colors"
                aria-label="Close modal"
              >
                <span className="material-symbols-outlined text-[20px]" style={{ color: 'var(--color-text-muted)' }}>
                  close
                </span>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label 
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Name *
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => {
                    setNewName(e.target.value);
                    setValidationError(null);
                  }}
                  placeholder="my-namespace"
                  className="w-full px-3 py-2 rounded-lg border text-sm"
                  style={{ 
                    background: 'var(--color-background)', 
                    borderColor: validationError ? 'var(--color-danger)' : 'var(--color-border)',
                    color: 'var(--color-text-main)'
                  }}
                  aria-describedby={validationError ? 'name-error' : undefined}
                />
                {validationError && (
                  <p id="name-error" className="text-xs mt-1" style={{ color: 'var(--color-danger)' }}>
                    {validationError}
                  </p>
                )}
                <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-faint)' }}>
                  Lowercase letters, numbers, underscores, and hyphens only. Max 64 chars.
                </p>
              </div>

              <div>
                <label 
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Description (optional)
                </label>
                <textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Describe this knowledge namespace..."
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg border text-sm resize-none"
                  style={{ 
                    background: 'var(--color-background)', 
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-main)'
                  }}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setNewName('');
                  setNewDescription('');
                  setValidationError(null);
                }}
                className="px-4 py-2 rounded-lg text-xs font-medium transition-colors"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={isCreating || !newName.trim()}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {isCreating ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div 
            className="rounded-2xl border p-6 w-full max-w-sm mx-4"
            style={{ 
              background: 'var(--color-surface)', 
              borderColor: 'var(--color-border)' 
            }}
          >
            <div className="flex items-center gap-3 mb-4">
              <span 
                className="material-symbols-outlined text-[24px]"
                style={{ color: 'var(--color-danger)' }}
              >
                warning
              </span>
              <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-main)' }}>
                Delete Namespace?
              </h3>
            </div>
            <p className="text-sm mb-6" style={{ color: 'var(--color-text-muted)' }}>
              Are you sure you want to delete <strong>"{deleteConfirm}"</strong>? This will remove all indexed files, chunks, and entities. This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 rounded-lg text-xs font-medium transition-colors"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                disabled={isDeleting}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-danger text-white hover:bg-danger/90 transition-colors disabled:opacity-50"
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
