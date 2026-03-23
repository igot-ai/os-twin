'use client';

import { useState, useCallback } from 'react';
import { Project, BrowseResult, DirEntry } from '@/types';
import { apiFetch } from '@/lib/api';

const PROJECT_COLORS = [
  'var(--purple)',
  'var(--cyan)',
  'var(--green)',
  'var(--amber)',
  'var(--orange)',
  'var(--red)',
  '#6ee7b7',
  '#93c5fd',
];

interface ProjectListProps {
  projects: Project[];
  loading: boolean;
  onSelectProject: (project: Project) => void;
  onCreated?: (planId: string) => void;
}

export default function ProjectList({
  projects,
  loading,
  onSelectProject,
  onCreated,
}: ProjectListProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [browseResult, setBrowseResult] = useState<BrowseResult | null>(null);
  const [selectedPath, setSelectedPath] = useState('~');
  const [projectName, setProjectName] = useState('');
  const [planContent, setPlanContent] = useState('');
  const [createStatus, setCreateStatus] = useState('');

  const browseFolder = useCallback(async (path: string | null) => {
    try {
      const url = path ? `/api/fs/browse?path=${encodeURIComponent(path)}` : '/api/fs/browse';
      const res = await apiFetch(url);
      if (!res.ok) throw new Error('Failed to browse');
      const data: BrowseResult = await res.json();
      setBrowseResult(data);
      setSelectedPath(data.current);
    } catch (err) {
      console.error('Browse error:', err);
    }
  }, []);

  const handleCreate = useCallback(async () => {
    if (!selectedPath || selectedPath === '~') {
      setCreateStatus('Please select a project directory.');
      return;
    }
    setCreateStatus('Creating project...');
    try {
      const body: Record<string, string> = {
        path: selectedPath,
        title: projectName || 'Untitled',
      };
      if (planContent) body.content = planContent;

      const res = await apiFetch('/api/plans/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setCreateStatus('');
      setShowCreate(false);
      setProjectName('');
      setPlanContent('');
      setSelectedPath('~');
      setBrowseResult(null);
      onCreated?.(data.plan_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setCreateStatus(`Error: ${msg}`);
    }
  }, [selectedPath, projectName, planContent, onCreated]);

  const openCreateForm = useCallback(() => {
    setShowCreate(true);
    browseFolder(null);
  }, [browseFolder]);

  const cancelCreate = useCallback(() => {
    setShowCreate(false);
    setCreateStatus('');
    setProjectName('');
    setPlanContent('');
    setSelectedPath('~');
    setBrowseResult(null);
  }, []);

  if (loading) {
    return (
      <div className="empty-state">
        <span className="empty-icon">◆</span>
        <p>Loading projects...</p>
      </div>
    );
  }

  return (
    <div className="project-list">
      <div className="project-list-header">
        <span className="project-list-count">
          {projects.length} project{projects.length !== 1 ? 's' : ''}
        </span>
        <button className="btn-outline" onClick={showCreate ? cancelCreate : openCreateForm}>
          {showCreate ? 'Cancel' : '+ New Project'}
        </button>
      </div>

      {showCreate && (
        <div className="np-form">
          <label className="field-label">Project Directory</label>
          <div className="np-browser">
            <div className="np-breadcrumb">
              <span className="np-breadcrumb-link" onClick={() => browseFolder('/')}>
                /
              </span>
              {browseResult &&
                browseResult.current
                  .split('/')
                  .filter(Boolean)
                  .map((part, i, arr) => {
                    const accPath = '/' + arr.slice(0, i + 1).join('/');
                    const isLast = i === arr.length - 1;
                    return (
                      <span key={i}>
                        <span className="np-breadcrumb-sep">/</span>
                        {isLast ? (
                          <span className="np-breadcrumb-current">{part}</span>
                        ) : (
                          <span className="np-breadcrumb-link" onClick={() => browseFolder(accPath)}>
                            {part}
                          </span>
                        )}
                      </span>
                    );
                  })}
            </div>

            <div className="np-dir-list">
              {browseResult?.parent && (
                <div
                  className="np-dir-item"
                  onClick={() => browseFolder(browseResult.parent!)}
                >
                  <span style={{ opacity: 0.6 }}>📁</span>
                  <span>..</span>
                </div>
              )}
              {browseResult?.dirs.length === 0 && (
                <div className="np-dir-empty">No subdirectories</div>
              )}
              {browseResult?.dirs.map((d: DirEntry) => (
                <div key={d.path} className="np-dir-item" onClick={() => browseFolder(d.path)}>
                  <span>📁</span>
                  <span style={{ flex: 1 }}>{d.name}</span>
                  {d.has_children && <span className="np-dir-arrow">›</span>}
                </div>
              ))}
            </div>

            <div className="np-selected-bar">
              <span className="np-selected-label">Selected:</span>
              <span className="np-selected-path">{selectedPath}</span>
            </div>
          </div>

          <label className="field-label">Project Name</label>
          <input
            type="text"
            className="np-input"
            placeholder="My New Project"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
          />

          <label className="field-label">Basic Plan (optional)</label>
          <textarea
            className="np-textarea"
            placeholder="Describe your project goals here..."
            value={planContent}
            onChange={(e) => setPlanContent(e.target.value)}
          />

          <div className="np-actions">
            <button className="btn-outline" onClick={cancelCreate}>
              Cancel
            </button>
            <button className="launch-btn" style={{ padding: '6px 14px', fontSize: '0.8rem' }} onClick={handleCreate}>
              Create & Open
            </button>
          </div>

          {createStatus && <div className="np-status">{createStatus}</div>}
        </div>
      )}

      {projects.length === 0 && !showCreate ? (
        <div className="empty-state">
          <span className="empty-icon">◆</span>
          <p>No projects yet.</p>
          <button className="empty-create-btn" onClick={openCreateForm}>
            Create Your First Project
          </button>
        </div>
      ) : (
        <div className="project-rows">
          {projects.map((project, i) => (
            <button
              key={project.path}
              className="project-row"
              onClick={() => onSelectProject(project)}
            >
              <span
                className="project-dot"
                style={{ background: PROJECT_COLORS[i % PROJECT_COLORS.length] }}
              />
              <span className="project-name">{project.name}</span>
              <span className="project-meta">
                {project.planCount} plan{project.planCount !== 1 ? 's' : ''}
                <span className="meta-sep">&middot;</span>
                {project.epicCount} epic{project.epicCount !== 1 ? 's' : ''}
              </span>
              <span className="project-path">{project.path}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
