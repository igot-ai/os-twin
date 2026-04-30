'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { TaskNode } from '@/lib/epic-parser';
import { Badge } from '@/components/ui/Badge';
import { MarkdownRenderer } from '@/lib/markdown-renderer';

// ── Types ───────────────────────────────────────────────────────────────────

export interface DraggableTaskCardProps {
  /** The task data */
  task: TaskNode;
  /** Index of this task in the list (used for drag-and-drop) */
  index: number;
  /** Whether this card is currently being dragged over (drop target highlight) */
  isDragOver: boolean;
  /** Called when the checkbox is toggled */
  onToggle: (index: number) => void;
  /** Called when the task title is committed after editing */
  onEditTitle: (index: number, newTitle: string) => void;
  /** Called when the task body is committed after editing */
  onEditBody: (index: number, newBody: string) => void;
  /** Called when the delete button is clicked */
  onDelete: (index: number) => void;
  /** Called when a drag starts on this card */
  onDragStart: (index: number) => void;
  /** Called when a drag ends */
  onDragEnd: () => void;
  /** Called when another card is dragged over this one */
  onDragOver: (index: number) => void;
  /** Called when a card is dropped on this one */
  onDrop: (index: number) => void;
  /** Render inline code and highlight spans */
  renderInlineCode?: (text: string) => React.ReactNode[];
}

// ── Component ───────────────────────────────────────────────────────────────

export function DraggableTaskCard({
  task,
  index,
  isDragOver,
  onToggle,
  onEditTitle,
  onEditBody,
  onDelete,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
  renderInlineCode,
}: DraggableTaskCardProps) {
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState(task.title);
  const [isEditingBody, setIsEditingBody] = useState(false);
  const [editBody, setEditBody] = useState(task.body);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isDeleteConfirming, setIsDeleteConfirming] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const bodyTextareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync edit state when task changes externally and not editing
  useEffect(() => {
    if (!isEditingTitle) setEditTitle(task.title);
  }, [task.title, isEditingTitle]);

  useEffect(() => {
    if (!isEditingBody) setEditBody(task.body);
  }, [task.body, isEditingBody]);

  // Auto-expand when body has content
  useEffect(() => {
    if (task.body && !isEditingBody) {
      // Keep collapsed by default, user can expand
    }
  }, [task.body, isEditingBody]);

  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus();
      titleInputRef.current.select();
    }
  }, [isEditingTitle]);

  useEffect(() => {
    if (isEditingBody && bodyTextareaRef.current) {
      bodyTextareaRef.current.focus();
    }
  }, [isEditingBody]);

  // Cleanup delete timer on unmount
  useEffect(() => {
    return () => {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
    };
  }, []);

  // ── Title editing ───────────────────────────────────────────────────────

  const handleStartEditTitle = useCallback(() => {
    setIsEditingTitle(true);
    setEditTitle(task.title);
  }, [task.title]);

  const handleCommitTitle = useCallback(() => {
    const trimmed = editTitle.trim();
    if (trimmed && trimmed !== task.title) {
      onEditTitle(index, trimmed);
    }
    setIsEditingTitle(false);
  }, [editTitle, task.title, index, onEditTitle]);

  const handleCancelTitle = useCallback(() => {
    setIsEditingTitle(false);
    setEditTitle(task.title);
  }, [task.title]);

  // ── Body editing ────────────────────────────────────────────────────────

  const handleStartEditBody = useCallback(() => {
    setIsEditingBody(true);
    setEditBody(task.body);
    setIsExpanded(true);
  }, [task.body]);

  const handleCommitBody = useCallback(() => {
    if (editBody !== task.body) {
      onEditBody(index, editBody);
    }
    setIsEditingBody(false);
  }, [editBody, task.body, index, onEditBody]);

  const handleCancelBody = useCallback(() => {
    setIsEditingBody(false);
    setEditBody(task.body);
  }, [task.body]);

  // ── Delete ──────────────────────────────────────────────────────────────

  const handleDeleteClick = useCallback(() => {
    if (isDeleteConfirming) {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
      setIsDeleteConfirming(false);
      onDelete(index);
    } else {
      setIsDeleteConfirming(true);
      deleteTimerRef.current = setTimeout(() => {
        setIsDeleteConfirming(false);
      }, 3000);
    }
  }, [isDeleteConfirming, index, onDelete]);

  // ── Drag handlers ───────────────────────────────────────────────────────

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

  // ── Render helpers ──────────────────────────────────────────────────────

  const displayTitle = renderInlineCode ? renderInlineCode(task.title) : task.title;

  return (
    <div
      className={`rounded-lg border transition-all ${
        isEditingTitle || isEditingBody
          ? 'border-primary bg-background shadow-md'
          : isDeleteConfirming
            ? 'border-red-300 bg-red-50/50 ring-1 ring-red-200'
            : isDragging
              ? 'border-primary/30 bg-primary/5 opacity-50 scale-[0.98]'
              : isDragOver
                ? 'border-primary/40 bg-primary/5 shadow-sm'
                : 'border-border bg-background/50 hover:border-text-faint'
      }`}
      draggable={!isEditingTitle && !isEditingBody}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={handleDragOverEvent}
      onDrop={handleDrop}
    >
      <div className="p-3">
        <div className="flex items-start gap-3">
          {/* Drag handle */}
          <div
            className={`flex items-center justify-center pt-1 cursor-grab active:cursor-grabbing transition-opacity shrink-0 ${
              isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
            }`}
            title="Drag to reorder"
          >
            <span className="material-symbols-outlined text-[14px] text-text-faint">drag_indicator</span>
          </div>

          {/* Checkbox */}
          <input
            type="checkbox"
            checked={task.completed}
            onChange={() => onToggle(index)}
            className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary/20 cursor-pointer shrink-0"
          />

          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Title row */}
            <div className="flex items-center gap-2 mb-0.5">
              <Badge variant="outline" className="font-mono text-[9px] px-1 py-0 h-4 shrink-0">
                {task.id}
              </Badge>
              {isEditingTitle ? (
                <input
                  ref={titleInputRef}
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.preventDefault(); handleCommitTitle(); }
                    if (e.key === 'Escape') handleCancelTitle();
                  }}
                  onBlur={handleCommitTitle}
                  className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-0.5 rounded text-sm font-bold text-text-main focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all min-w-0"
                  autoFocus
                />
              ) : (
                <span
                  className={`text-sm font-bold truncate cursor-text hover:bg-surface-hover/30 px-1 -mx-1 rounded transition-colors ${
                    task.completed ? 'text-text-muted line-through' : 'text-text-main'
                  }`}
                  onClick={handleStartEditTitle}
                  title="Click to edit title"
                >
                  {displayTitle}
                </span>
              )}
            </div>

            {/* Body section */}
            {task.body && !isEditingBody && (
              <div className="ml-0">
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="flex items-center gap-1 text-[10px] text-text-faint hover:text-text-main transition-colors mt-1"
                >
                  <span
                    className="material-symbols-outlined text-[14px] transition-transform"
                    style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }}
                  >
                    chevron_right
                  </span>
                  {isExpanded ? 'Hide details' : 'Show details'}
                </button>
                {isExpanded && (
                  <div
                    className="mt-2 pl-2 border-l-2 border-border cursor-text hover:bg-surface-hover/30 p-2 -m-1 rounded transition-colors"
                    onDoubleClick={handleStartEditBody}
                    title="Double-click to edit details"
                  >
                    <MarkdownRenderer content={task.body} className="text-xs text-text-muted" />
                  </div>
                )}
              </div>
            )}

            {/* Body editing mode */}
            {isEditingBody && (
              <div className="mt-2 space-y-2">
                <textarea
                  ref={bodyTextareaRef}
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  placeholder="Task details (markdown supported)…"
                  className="w-full bg-background border border-border focus:border-primary px-3 py-2 rounded text-xs text-text-main font-mono min-h-[80px] focus:outline-none focus:ring-2 focus:ring-primary/20 resize-y transition-all placeholder:text-text-faint/40"
                  rows={Math.max(3, editBody.split('\n').length + 1)}
                  autoFocus
                />
                <div className="flex items-center gap-2 justify-end">
                  <button
                    onMouseDown={(e) => { e.preventDefault(); handleCancelBody(); }}
                    className="px-3 py-1 text-[10px] font-bold text-text-faint hover:text-text-main rounded-md border border-border hover:bg-surface-hover transition-all uppercase tracking-wider"
                  >
                    Cancel
                  </button>
                  <button
                    onMouseDown={(e) => { e.preventDefault(); handleCommitBody(); }}
                    className="px-3 py-1 text-[10px] font-bold text-white bg-primary hover:bg-primary-dark rounded-md shadow-sm transition-all uppercase tracking-wider"
                  >
                    Save
                  </button>
                </div>
              </div>
            )}

            {/* Add body button when no body exists */}
            {!task.body && !isEditingBody && (
              <button
                onClick={handleStartEditBody}
                className="flex items-center gap-1 text-[10px] text-text-faint hover:text-primary transition-colors mt-1"
              >
                <span className="material-symbols-outlined text-[12px]">add</span>
                Add details
              </button>
            )}
          </div>

          {/* Delete button */}
          <button
            onClick={handleDeleteClick}
            className={`p-1 rounded transition-all shrink-0 ${
              isDeleteConfirming
                ? 'bg-red-100 text-red-600 hover:bg-red-200'
                : 'hover:bg-red-50 text-text-faint hover:text-red-500'
            }`}
            title={isDeleteConfirming ? 'Click again to confirm delete' : 'Delete task'}
          >
            <span className="material-symbols-outlined text-[16px]">
              {isDeleteConfirming ? 'delete' : 'delete_outline'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
