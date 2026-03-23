'use client';

import { useState, useCallback } from 'react';
import { Project } from '@/types';
import { useApp } from '@/contexts/AppContext';
import { useProjects } from '@/hooks/useProjects';
import ProjectList from '@/components/projects/ProjectList';
import ProjectDetail from '@/components/projects/ProjectDetail';

export default function ProjectsPage() {
  const { openPlanEditor } = useApp();
  const { projects, loading, reload } = useProjects();
  const [selected, setSelected] = useState<Project | null>(null);

  const colorIndex = selected ? projects.findIndex((p) => p.path === selected.path) : 0;

  const handleCreated = useCallback(
    (planId: string) => {
      reload();
      openPlanEditor(planId);
    },
    [reload, openPlanEditor],
  );

  if (selected) {
    return (
      <div className="projects-page">
        <ProjectDetail
          project={selected}
          colorIndex={colorIndex}
          onBack={() => setSelected(null)}
          onOpenPlan={openPlanEditor}
        />
      </div>
    );
  }

  return (
    <div className="projects-page">
      <div className="page-header">
        <h1 className="page-title">Projects</h1>
      </div>
      <ProjectList
        projects={projects}
        loading={loading}
        onSelectProject={setSelected}
        onCreated={handleCreated}
      />
    </div>
  );
}
