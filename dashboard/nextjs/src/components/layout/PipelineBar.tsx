'use client';

import { Room } from '@/types';
import { PIPELINE_MAP } from '@/lib/constants';

interface PipelineBarProps {
  rooms: Room[];
}

const steps = [
  { id: 'pipe-manager', icon: '⬡', label: 'MANAGER' },
  { id: 'pipe-engineer', icon: '⚙', label: 'ENGINEER' },
  { id: 'pipe-qa', icon: '✦', label: 'QA' },
  { id: 'pipe-release', icon: '◆', label: 'RELEASE' },
];

function PipelineArrow({ active }: { active?: boolean }) {
  return (
    <div className={`pipeline-arrow${active ? ' active' : ''}`}>
      <svg width="60" height="16" viewBox="0 0 60 16">
        <line
          x1="0"
          y1="8"
          x2="50"
          y2="8"
          stroke="currentColor"
          strokeWidth="1"
          strokeDasharray="4 3"
        >
          <animate
            attributeName="stroke-dashoffset"
            from="14"
            to="0"
            dur="0.8s"
            repeatCount="indefinite"
          />
        </line>
        <polygon points="50,4 60,8 50,12" fill="currentColor" />
      </svg>
    </div>
  );
}

export default function PipelineBar({ rooms }: PipelineBarProps) {
  const isActive = (id: string) => {
    const statuses = PIPELINE_MAP[id];
    if (!statuses) return false;
    return rooms.some((r) => statuses.includes(r.status));
  };

  return (
    <div className="pipeline-bar" id="pipeline-bar">
      {steps.map((step, i) => (
        <div key={step.id} style={{ display: 'contents' }}>
          <div
            className={`pipeline-step${isActive(step.id) ? ' pipe-active' : ''}`}
            id={step.id}
          >
            <span className="pipe-icon">{step.icon}</span>
            <span>{step.label}</span>
          </div>
          {i < steps.length - 1 && <PipelineArrow active={isActive(step.id)} />}
        </div>
      ))}
    </div>
  );
}
