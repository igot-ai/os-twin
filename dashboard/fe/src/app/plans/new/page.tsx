'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/Button';
import { apiPost } from '@/lib/api-client';
import { PLAN_TEMPLATES } from '@/lib/plan-templates';
import { usePlanRefine } from '@/hooks/use-plan-refine';
import FolderBrowser from '@/components/plan/FolderBrowser';
import AIChatPanel from '@/components/plan/AIChatPanel';

interface CreatePlanResponse {
  plan_id: string;
  url: string;
  title: string;
  path: string;
  working_dir: string;
  filename: string;
}

export default function NewPlanPage() {
  const router = useRouter();
  const [path, setPath] = useState('');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const {
    chatHistory,
    isRefining,
    streamedResponse,
    error: refineError,
    refine,
    cancelRefine,
    clearHistory,
  } = usePlanRefine();

  const handleCreate = async () => {
    setError('');

    if (!path.trim()) {
      setError('Project path is required.');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await apiPost<CreatePlanResponse>('/plans/create', {
        path: path.trim(),
        title: title.trim() || 'Untitled',
        content: content.trim(),
      });
      router.push(`/plans/${result.plan_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create plan.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const parsedEpics = useMemo(() => {
    if (!content.trim()) return [];
    const epicRegex = /^## (EPIC-\d+|Epic:\s*\S+|Task:\s*\S+)\s*[—\-]?\s*(.*)/gm;
    const epics: { ref: string; title: string }[] = [];
    let match;
    while ((match = epicRegex.exec(content)) !== null) {
      const ref = match[1].replace(/^(Epic|Task):\s*/, '').trim();
      epics.push({ ref, title: match[2]?.trim() || ref });
    }
    return epics;
  }, [content]);

  const handleApplyTemplate = (key: string) => {
    const template = PLAN_TEMPLATES[key];
    if (!template) return;
    setTitle(template.title);
    setContent(template.content);
  };

  return (
    <div className="h-screen flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <Link
          href="/"
          className="text-sm text-text-muted hover:text-text-main flex items-center gap-1 transition-colors"
        >
          <span className="material-symbols-outlined text-sm">arrow_back</span>
          Back to Command Center
        </Link>
        <h1 className="text-2xl font-extrabold tracking-tight text-text-main">
          Create New Plan
        </h1>
      </div>

      {/* Two-column body */}
      <div className="flex flex-1 min-h-0">
        {/* Left column */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {/* Project Directory */}
          <div>
            <label className="text-sm font-semibold text-text-main mb-2 block">
              Project Directory
            </label>
            <FolderBrowser selectedPath={path} onSelectPath={setPath} />
            {path && (
              <p className="font-mono text-sm text-primary mt-2">{path}</p>
            )}
          </div>

          {/* Plan Title */}
          <div>
            <label htmlFor="plan-title" className="text-sm font-semibold text-text-main mb-2 block">
              Plan Title
            </label>
            <input
              id="plan-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="My New Project"
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text-main placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            />
          </div>

          {/* Plan Content */}
          <div>
            <label htmlFor="plan-content" className="text-sm font-semibold text-text-main mb-2 block">
              Plan Content
            </label>
            <textarea
              id="plan-content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="# Plan: Your Project Name&#10;&#10;## Config&#10;working_dir: .&#10;&#10;## EPIC-001 - Your first epic&#10;&#10;Role: engineer&#10;Objective: ...&#10;Skills: ...&#10;&#10;Description of work...&#10;&#10;Acceptance criteria:&#10;- ..."
              className="w-full h-[250px] px-3 py-2 rounded-lg border border-border bg-background font-mono text-sm text-text-main placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y custom-scrollbar"
            />
          </div>

          {/* Quick Templates */}
          <div>
            <label className="text-sm font-semibold text-text-main mb-2 block">
              Quick Templates
            </label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(PLAN_TEMPLATES).map(([key, template]) => (
                <Button
                  key={key}
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => handleApplyTemplate(key)}
                >
                  {template.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Parsed Epics Preview */}
          {parsedEpics.length > 0 && (
            <div>
              <label className="text-sm font-semibold text-text-main mb-2 block">
                Epics Preview
                <span className="ml-2 text-xs font-normal text-text-muted">
                  {parsedEpics.length} epic{parsedEpics.length !== 1 ? 's' : ''} detected
                </span>
              </label>
              <div className="grid grid-cols-2 gap-2">
                {parsedEpics.map((epic) => (
                  <div
                    key={epic.ref}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-border bg-surface"
                  >
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: 18 }}>
                      task_alt
                    </span>
                    <div className="min-w-0">
                      <span className="text-xs font-semibold font-mono text-primary">{epic.ref}</span>
                      <p className="text-xs text-text-muted truncate">{epic.title}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div
              className="rounded-lg px-4 py-3 text-sm font-medium"
              style={{ background: 'rgba(239, 68, 68, 0.08)', color: 'var(--color-danger)' }}
            >
              {error}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex justify-end gap-3 mt-6">
            <Button variant="outline" type="button" onClick={() => router.push('/')}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="button"
              isLoading={isSubmitting}
              disabled={!path.trim()}
              onClick={handleCreate}
            >
              Create &amp; Open
            </Button>
          </div>
        </div>

        {/* Right column - AI Chat */}
        <div className="w-[400px] border-l border-border bg-surface shrink-0">
          <AIChatPanel
            chatHistory={chatHistory}
            isRefining={isRefining}
            streamedResponse={streamedResponse}
            error={refineError}
            onSendMessage={(message) => refine(message, content, '')}
            onApplyToEditor={(extractedContent) => setContent(extractedContent)}
            onCancel={cancelRefine}
            onClearHistory={clearHistory}
          />
        </div>
      </div>
    </div>
  );
}
