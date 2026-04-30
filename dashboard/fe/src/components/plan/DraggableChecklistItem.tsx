'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { CheckItem } from '@/lib/epic-parser';

// ── Types ───────────────────────────────────────────────────────────────────

export interface DraggableChecklistItemProps {
  /** The checklist item data */
  item: CheckItem;
  /** Index of this item in the list (used for drag-and-drop) */
  index: number;
  /** Whether this item is currently being dragged over (drop target highlight) */
  isDragOver: boolean;
  /** Whether AC styling should be used (green/red instead of primary) */
  isAC?: boolean;
  /** Called when the checkbox is toggled */
  onToggle: (index: number) => void;
  /** Called when the item text is committed after editing */
  onEdit: (index: number, newText: string) => void;
  /** Called when the delete button is clicked */
  onDelete: (index: number) => void;
  /** Called when a drag starts on this item */
  onDragStart: (index: number) => void;
  /** Called when a drag ends */
  onDragEnd: () => void;
  /** Called when another item is dragged over this one */
  onDragOver: (index: number) => void;
  /** Called when an item is dropped on this one */
  onDrop: (index: number) => void;
  /** Called to move focus to the next item (Tab key) */
  onNextItem?: () => void;
}

// ── Component ───────────────────────────────────────────────────────────────

export function DraggableChecklistItem({
  item,
  index,
  isDragOver,
  isAC = false,
  onToggle,
  onEdit,
  onDelete,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
  onNextItem,
}: DraggableChecklistItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(item.text);
  const [isDeleteConfirming, setIsDeleteConfirming] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  // Sync edit text when item changes externally and not editing
  useEffect(() => {
    if (!isEditing) {
      setEditText(item.text);
    }
  }, [item.text, isEditing]);

  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [isEditing]);

  // Cleanup delete timer on unmount
  useEffect(() => {
    return () => {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
    };
  }, []);

  const handleStartEdit = useCallback(() => {
    setIsEditing(true);
    setEditText(item.text);
  }, [item.text]);

  const handleCommitEdit = useCallback(() => {
    const trimmed = editText.trim();
    if (trimmed && trimmed !== item.text) {
      onEdit(index, trimmed);
    }
    setIsEditing(false);
  }, [editText, item.text, index, onEdit]);

  const handleCancelEdit = useCallback(() => {
    setIsEditing(false);
    setEditText(item.text);
  }, [item.text]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleCommitEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    } else if (e.key === 'Tab') {
      handleCommitEdit();
      if (onNextItem) onNextItem();
    }
  }, [handleCommitEdit, handleCancelEdit, onNextItem]);

  const handleDeleteClick = useCallback(() => {
    if (isDeleteConfirming) {
      // Second click: actually delete
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
      setIsDeleteConfirming(false);
      onDelete(index);
    } else {
      // First click: show confirmation
      setIsDeleteConfirming(true);
      // Auto-dismiss after 3 seconds
      deleteTimerRef.current = setTimeout(() => {
        setIsDeleteConfirming(false);
      }, 3000);
    }
  }, [isDeleteConfirming, index, onDelete]);

  // ── Drag handlers ─────────────────────────────────────────────────────────

  const handleDragStart = useCallback((e: React.DragEvent) => {
    setIsDragging(true);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
    onDragStart(index);
  }, [index, onDragStart]);

  const handleDragEnd = useCallback(() => {
    setIsDragging(false);
    onDragEnd();
  }, [onDragEnd]);

  const handleDragOverEvent = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    onDragOver(index);
  }, [index, onDragOver]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    onDrop(index);
  }, [index, onDrop]);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div
      className={`flex items-start gap-2 group/item px-1 -mx-1 rounded transition-all py-1 ${
        isDragging ? 'opacity-40 scale-[0.98]' : ''
      } ${
        isDragOver ? 'bg-primary/8 border-t-2 border-primary/40 -mt-0.5 pt-1.5' : ''
      } ${
        isDeleteConfirming ? 'bg-red-50 ring-1 ring-red-200' : 'hover:bg-surface-hover/30'
      }`}
      draggable={!isEditing}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={handleDragOverEvent}
      onDrop={handleDrop}
    >
      {/* Drag handle */}
      <div
        className={`flex items-center justify-center pt-0.5 cursor-grab active:cursor-grabbing transition-opacity shrink-0 ${
          isDragging ? 'opacity-100' : 'opacity-0 group-hover/item:opacity-100'
        }`}
        title="Drag to reorder"
      >
        <span className="material-symbols-outlined text-[14px] text-text-faint">drag_indicator</span>
      </div>

      {/* Checkbox */}
      <input
        type="checkbox"
        checked={item.checked}
        onChange={() => onToggle(index)}
        className={`mt-1 h-3.5 w-3.5 rounded border-border focus:ring-primary/20 cursor-pointer shrink-0 ${
          isAC ? (item.checked ? 'text-success' : 'text-danger') : 'text-primary'
        }`}
      />

      {/* Text / Edit input */}
      {isEditing ? (
        <input
          ref={editInputRef}
          type="text"
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleCommitEdit}
          className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-0.5 rounded text-sm text-text-main focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all min-w-0"
        />
      ) : (
        <span
          className={`flex-1 text-sm leading-relaxed transition-colors cursor-text min-w-0 ${
            item.checked
              ? (isAC ? 'text-success-text font-medium' : 'text-text-muted line-through')
              : (isAC ? 'text-danger-text' : 'text-text-main')
          }`}
          onClick={handleStartEdit}
          title="Click to edit"
        >
          {item.text}
        </span>
      )}

      {/* Delete button */}
      <button
        onClick={handleDeleteClick}
        className={`p-0.5 rounded transition-all mt-0.5 shrink-0 ${
          isDeleteConfirming
            ? 'bg-red-100 text-red-600 hover:bg-red-200 opacity-100'
            : 'opacity-0 group-hover/item:opacity-100 hover:bg-red-50 text-text-faint hover:text-red-500'
        }`}
        title={isDeleteConfirming ? 'Click again to confirm delete' : 'Delete item'}
      >
        <span className="material-symbols-outlined text-[14px]">
          {isDeleteConfirming ? 'delete' : 'close'}
        </span>
      </button>
    </div>
  );
}
