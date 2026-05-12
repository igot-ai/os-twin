'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { TrailEntry, TrailAction } from '@/hooks/use-nexus-explorer';
import { FONT } from './typography';
import { Icon } from './Icon';

function trailIcon(action: TrailAction): string {
  switch (action.type) {
    case 'seed': return 'explore';
    case 'query': return 'search';
    case 'expand': return 'bubble';
    case 'search': return 'radar';
    case 'path': return 'route';
    case 'select': return 'touch_app';
  }
}

function trailLabel(action: TrailAction): string {
  switch (action.type) {
    case 'seed': return `seed(${action.topK})`;
    case 'query': return `"${action.query.slice(0, 24)}${action.query.length > 24 ? '…' : ''}"`;
    case 'expand': return `expand(${action.depth})`;
    case 'search': return `find("${action.query.slice(0, 16)}")`;
    case 'path': return `path`;
    case 'select': return action.nodeId.slice(0, 8);
  }
}

function trailColor(action: TrailAction): string {
  switch (action.type) {
    case 'seed': return '#6366f1';
    case 'query': return '#22d3ee';
    case 'expand': return '#a78bfa';
    case 'search': return '#34d399';
    case 'path': return '#fbbf24';
    case 'select': return '#94a3b8';
  }
}

interface ExplorationTrailProps {
  trail: TrailEntry[];
  docked?: boolean;
}

export default function ExplorationTrail({ trail, docked = false }: ExplorationTrailProps) {
  if (trail.length === 0) return null;

  const visible = trail.slice(0, 8);

  return (
    <div className={docked ? 'max-w-full' : 'absolute bottom-16 left-3 z-10 max-w-[280px]'}>
      <AnimatePresence mode="popLayout">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          className="flex flex-wrap items-center gap-1"
        >
          {visible.map((entry, i) => {
            const color = trailColor(entry.action);
            return (
              <React.Fragment key={entry.id}>
                {i > 0 && (
                  <span className={FONT.caption} style={{ color: 'var(--color-text-faint)' }}>→</span>                )}
                <div
                  className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded-md ${FONT.caption} font-medium`}
                  style={{
                    background: `${color}10`,
                    color,
                    border: `1px solid ${color}30`,
                  }}
                  title={trailLabel(entry.action)}
                >
                  <Icon name={trailIcon(entry.action)} size={10} />
                  <span className="truncate max-w-[60px]">{trailLabel(entry.action)}</span>
                </div>
              </React.Fragment>
            );
          })}
          {trail.length > 8 && (
            <span className={`${FONT.caption} px-1`} style={{ color: 'var(--color-text-faint)' }}>
              +{trail.length - 8}
            </span>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
