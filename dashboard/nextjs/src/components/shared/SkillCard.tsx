'use client';

import React from 'react';

interface SkillCardProps {
  name: string;
  description: string;
  tags: string[];
  trustLevel: string;
  source: string;
  onClick?: () => void;
}

const TRUST_COLORS: Record<string, string> = {
  core: 'var(--green)',
  verified: 'var(--cyan)',
  experimental: 'var(--amber)',
};

export default function SkillCard({
  name,
  description,
  tags,
  trustLevel,
  source,
  onClick,
}: SkillCardProps) {
  const trustColor = TRUST_COLORS[trustLevel] || 'var(--muted)';

  return (
    <div className="skill-card" onClick={onClick} role="button" tabIndex={0}>
      <div className="skill-card-header">
        <span className="skill-card-name">{name}</span>
        <span className="skill-trust-badge" style={{ borderColor: trustColor, color: trustColor }}>
          {trustLevel}
        </span>
      </div>
      <p className="skill-card-desc">{description || 'No description'}</p>
      <div className="skill-card-footer">
        <div className="skill-tags">
          {tags.map((tag) => (
            <span key={tag} className="skill-tag">{tag}</span>
          ))}
        </div>
        <span className="skill-source">{source}</span>
      </div>
    </div>
  );
}
