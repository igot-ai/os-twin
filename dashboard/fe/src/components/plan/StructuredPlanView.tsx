'use client';

import { useState } from 'react';
import { usePlanContext } from './PlanWorkspace';
import { EpicCardPreview } from './EpicCardPreview';
import { EpicNode } from '@/lib/epic-parser';
import { Badge } from '@/components/ui/Badge';
import { MarkdownRenderer } from '@/lib/markdown-renderer';

export function StructuredPlanView() {
  const { parsedPlan, updateParsedPlan, setActiveTab } = usePlanContext();
  const [editingPlanTitle, setEditingPlanTitle] = useState(false);
  const [editingGoal, setEditingGoal] = useState(false);
  
  const [planTitleValue, setPlanTitleValue] = useState(parsedPlan?.title.replace(/^#\s*/, '') || '');
  const [goalValue, setGoalValue] = useState(parsedPlan?.preamble || '');

  // Sync state with props when NOT editing
  if (parsedPlan) {
    const currentDisplayTitle = parsedPlan.title.replace(/^#\s*/, '');
    if (!editingPlanTitle && planTitleValue !== currentDisplayTitle) {
      setPlanTitleValue(currentDisplayTitle);
    }
    if (!editingGoal && goalValue !== parsedPlan.preamble) {
      setGoalValue(parsedPlan.preamble);
    }
  }

  if (!parsedPlan) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-10 text-center">
        <span className="material-symbols-outlined text-danger text-5xl mb-4">error</span>
        <h3 className="text-xl font-bold text-text-main mb-2">Parse Error or Empty Plan</h3>
        <p className="text-text-muted mb-6 max-w-md">
          We couldn&apos;t parse the plan structure. This might be due to invalid EPIC formatting or the file not being a plan.
        </p>
        <button
          onClick={() => setActiveTab('editor')}
          className="px-4 py-2 bg-primary text-white font-bold rounded-lg shadow hover:bg-primary-dark transition-colors"
        >
          Switch to Edit Mode
        </button>
      </div>
    );
  }

  const handlePlanTitleSubmit = () => {
    setEditingPlanTitle(false);
    const newFullTitle = planTitleValue.startsWith('# ') ? planTitleValue : `# ${planTitleValue}`;
    if (newFullTitle !== parsedPlan.title) {
      updateParsedPlan((doc) => {
        doc.title = newFullTitle;
        return doc;
      });
    }
  };

  const handleGoalSubmit = () => {
    setEditingGoal(false);
    if (goalValue !== parsedPlan.preamble) {
      updateParsedPlan((doc) => {
        doc.preamble = goalValue;
        return doc;
      });
    }
  };

  const handleAddEpic = () => {
    updateParsedPlan((doc) => {
      const lastEpic = doc.epics[doc.epics.length - 1];
      let nextNum = 1;
      if (lastEpic) {
        const match = lastEpic.ref.match(/EPIC-(\d+)/);
        if (match) nextNum = parseInt(match[1]) + 1;
      }
      const newRef = `EPIC-${nextNum.toString().padStart(3, '0')}`;
      
      const newEpic: EpicNode = {
        ref: newRef,
        title: 'New Feature',
        headingLevel: 2,
        rawHeading: `## ${newRef} — New Feature`,
        frontmatter: new Map([
          ['Phase', '1'],
          ['Owner', 'engineer'],
          ['Priority', 'P0']
        ]),
        sections: [
          {
            heading: 'Description',
            headingLevel: 3,
            sectionKey: 'description',
            type: 'text',
            content: 'Description of the new feature.',
            rawLines: ['### Description', 'Description of the new feature.'],
            preamble: [],
            postamble: []
          },
          {
            heading: 'Definition of Done',
            headingLevel: 3,
            sectionKey: 'definition_of_done',
            type: 'checklist',
            content: '',
            items: [
              { text: 'Feature implemented', checked: false, rawLine: '- [ ] Feature implemented', prefix: '- [ ] ' }
            ],
            rawLines: ['### Definition of Done', '- [ ] Feature implemented'],
            preamble: [],
            postamble: []
          },
          {
            heading: 'Tasks',
            headingLevel: 3,
            sectionKey: 'tasks',
            type: 'tasklist',
            content: '',
            tasks: [
              {
                id: `T-G${nextNum.toString().padStart(3, '0')}.1`,
                title: 'Initial setup',
                completed: false,
                body: 'Acceptance Criteria:\n- Setup completed',
                bodyLines: ['Acceptance Criteria:', '- Setup completed'],
                rawHeader: `- [ ] **T-G${nextNum.toString().padStart(3, '0')}.1** — Initial setup`,
                prefix: '- [ ] ',
                idPrefix: '**',
                idSuffix: '**',
                delimiter: ' — '
              }
            ],
            rawLines: ['### Tasks', `- [ ] **T-G${nextNum.toString().padStart(3, '0')}.1** — Initial setup`, '  Acceptance Criteria:', '  - Setup completed'],
            preamble: [],
            postamble: []
          }
        ],
        depends_on: [],
        rawDependsOn: ''
      };
      
      doc.epics.push(newEpic);
      return doc;
    });
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar bg-background/30 p-6">
      <div className="max-w-5xl mx-auto space-y-8 pb-20">
        {/* Plan Header */}
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            {editingPlanTitle ? (
              <input
                type="text"
                value={planTitleValue}
                onChange={(e) => setPlanTitleValue(e.target.value)}
                onBlur={handlePlanTitleSubmit}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handlePlanTitleSubmit();
                  if (e.key === 'Escape') {
                    setEditingPlanTitle(false);
                    setPlanTitleValue(parsedPlan.title);
                  }
                }}
                className="bg-transparent border-b border-primary text-2xl font-black text-text-main w-full focus:outline-none"
                autoFocus
              />
            ) : (
              <h1 
                className="text-2xl font-black text-text-main hover:text-primary transition-colors cursor-text"
                onDoubleClick={() => setEditingPlanTitle(true)}
                data-testid="plan-title"
              >
                {parsedPlan.title.replace(/^#\s*/, '') || 'Untitled Plan'}
              </h1>
            )}
            <Badge variant="primary" size="md">PLAN</Badge>
          </div>

          <div className="p-4 rounded-xl border border-border bg-surface shadow-sm">
            <h4 className="text-[10px] font-bold text-text-faint uppercase tracking-widest mb-2">High-Level Goal & Configuration</h4>
            {editingGoal ? (
              <textarea
                value={goalValue}
                onChange={(e) => setGoalValue(e.target.value)}
                onBlur={handleGoalSubmit}
                className="w-full bg-background border border-primary px-3 py-2 rounded text-sm min-h-[80px] focus:outline-none focus:ring-2 focus:ring-primary/20 font-mono"
                autoFocus
              />
            ) : (
              <div 
                className="cursor-text hover:bg-surface-hover/30 p-2 -m-2 rounded transition-colors"
                onDoubleClick={() => setEditingGoal(true)}
                data-testid="plan-goal"
              >
                <MarkdownRenderer content={parsedPlan.preamble} className="text-sm text-text-main" />
              </div>
            )}
          </div>
        </div>

        {/* EPIC Cards */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-text-main flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">account_tree</span>
              Plan Architecture
            </h2>
            <Badge variant="muted">{parsedPlan.epics.length} EPICS</Badge>
          </div>
          
          {parsedPlan.epics.map((epic) => (
            <EpicCardPreview key={epic.ref} epic={epic} />
          ))}

          <button
            onClick={handleAddEpic}
            className="w-full py-4 rounded-xl border-2 border-dashed border-border hover:border-primary hover:bg-primary/5 text-text-muted hover:text-primary transition-all flex flex-col items-center justify-center gap-2 group"
          >
            <span className="material-symbols-outlined text-3xl group-hover:scale-110 transition-transform">add_circle</span>
            <span className="text-sm font-bold">Add New EPIC</span>
          </button>
        </div>
      </div>
    </div>
  );
}
