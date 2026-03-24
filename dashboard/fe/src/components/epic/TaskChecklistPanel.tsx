'use client';

import React, { useState } from 'react';
import { Task } from '@/types';
import { useEpic } from '@/hooks/use-epics';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragStartEvent,
  DragOverlay,
  defaultDropAnimationSideEffects,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

interface TaskItemProps {
  task: Task;
  onToggle: (task: Task) => void;
  isDragging?: boolean;
}

function TaskItem({ task, onToggle, isDragging }: TaskItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id: task.task_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 10 : undefined,
    opacity: isDragging ? 0.5 : undefined,
  };

  return (
    <div 
      ref={setNodeRef}
      style={style}
      className={`flex items-start gap-3 p-2.5 rounded border transition-colors group ${
        task.status === 'in-progress' 
          ? 'border-2 border-primary bg-primary-muted shadow-sm' 
          : task.completed
            ? 'border-border bg-surface-hover/50 opacity-80'
            : 'border-border hover:border-text-faint bg-surface'
      }`}
    >
      {/* Checkbox */}
      <input 
        type="checkbox" 
        checked={task.completed} 
        className={`mt-1 rounded border-border w-3.5 h-3.5 cursor-pointer z-10 ${
          task.status === 'in-progress' 
            ? 'border-primary text-primary focus:ring-primary' 
            : 'text-text-faint focus:ring-0'
        }`}
        onChange={(e) => {
          e.stopPropagation();
          onToggle(task);
        }}
        aria-label={`Mark task ${task.task_id} as ${task.completed ? 'incomplete' : 'complete'}`}
      />

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className={`text-[10px] font-mono ${task.status === 'in-progress' ? 'text-primary font-bold' : 'text-text-muted'}`}>
            {task.task_id}
          </span>
          <span 
            {...attributes} 
            {...listeners}
            className={`material-symbols-outlined text-xs opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing ${
              task.status === 'in-progress' ? 'text-primary/30' : 'text-text-faint'
            }`}
            aria-label="Drag to reorder"
            role="button"
          >
            drag_indicator
          </span>
        </div>
        <p className={`text-xs ${
          task.completed ? 'text-text-muted line-through truncate' : 'text-text-main font-semibold'
        }`}>
          {task.description}
        </p>
        
        <div className="flex items-center gap-2 mt-1">
          <span className={`text-[9px] px-1 rounded ${
            task.status === 'in-progress' 
              ? 'bg-primary-muted text-primary font-bold' 
              : 'bg-surface-hover text-text-muted border border-border'
          }`}>
            {task.assigned_role}
          </span>
          {task.status === 'in-progress' && (
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
          )}
          {task.completed_at && (
            <span className="text-[9px] text-text-faint">
              {new Date(task.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

interface TaskChecklistPanelProps {
  planId: string;
  epicRef: string;
  tasks: Task[];
}

export default function TaskChecklistPanel({ planId, epicRef, tasks }: TaskChecklistPanelProps) {
  const { updateTask, updateTaskOrder } = useEpic(planId, epicRef);
  const [activeId, setActiveId] = useState<string | null>(null);
  
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleToggleTask = async (task: Task) => {
    const newCompleted = !task.completed;
    try {
      await updateTask(task.task_id, { 
        completed: newCompleted,
        completed_at: newCompleted ? new Date().toISOString() : undefined,
        status: newCompleted ? 'done' : (task.status === 'done' ? 'pending' : task.status)
      });
    } catch (err) {
      console.error('Failed to toggle task:', err);
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);

    if (over && active.id !== over.id) {
      const oldIndex = tasks.findIndex((t) => t.task_id === active.id);
      const newIndex = tasks.findIndex((t) => t.task_id === over.id);
      
      const newOrder = arrayMove(tasks, oldIndex, newIndex);
      try {
        await updateTaskOrder(newOrder.map(t => t.task_id));
      } catch (err) {
        console.error('Failed to reorder tasks:', err);
      }
    }
  };

  const activeTask = activeId ? tasks.find(t => t.task_id === activeId) : null;
  const completedCount = tasks.filter(t => t.completed).length;
  const totalCount = tasks.length;

  return (
    <aside className="w-72 border-r border-border bg-surface flex flex-col shrink-0 overflow-hidden">
      {/* Sidebar Header */}
      <div className="p-4 border-b border-border bg-surface-hover/30 flex items-center justify-between">
        <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-sm" aria-hidden="true">checklist</span> Task Checklist
        </h2>
        <span className="text-[10px] font-mono bg-surface-hover px-1.5 py-0.5 rounded text-text-main">
          {completedCount}/{totalCount}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="px-4 py-2 border-b border-border bg-surface-hover/10">
        <div className="flex justify-between text-[10px] font-bold text-text-faint mb-1 uppercase tracking-wider">
          <span>Completion</span>
          <span>{totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0}%</span>
        </div>
        <div className="h-1.5 w-full bg-border rounded-full overflow-hidden shadow-inner">
          <div 
            className="h-full bg-primary transition-all duration-500 ease-out shadow-sm"
            style={{ width: `${totalCount > 0 ? (completedCount / totalCount) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Task List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3" role="list" aria-label="Tasks">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={tasks.map(t => t.task_id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-2">
              {tasks.map((task) => (
                <TaskItem 
                  key={task.task_id} 
                  task={task} 
                  onToggle={handleToggleTask} 
                />
              ))}
            </div>
          </SortableContext>
          <DragOverlay dropAnimation={{
            sideEffects: defaultDropAnimationSideEffects({
              styles: {
                active: {
                  opacity: '0.5',
                },
              },
            }),
          }}>
            {activeTask ? (
              <div className="w-full">
                <TaskItem task={activeTask} onToggle={handleToggleTask} isDragging />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>
    </aside>
  );
}
