'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api';
import SkillCard from '@/components/shared/SkillCard';

interface Skill {
  name: string;
  description: string;
  tags: string[];
  trust_level: string;
  source: string;
  path?: string;
  content?: string;
}

interface SkillsPanelProps {
  onClose: () => void;
}

export default function SkillsPanel({ onClose }: SkillsPanelProps) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [detail, setDetail] = useState<Skill | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    setLoading(true);
    try {
      let url = '/api/skills';
      const params = new URLSearchParams();
      if (search) {
        url = '/api/skills/search';
        params.set('q', search);
      }
      if (roleFilter) params.set('role', roleFilter);
      if (activeTag) params.append('tags', activeTag);
      const query = params.toString();
      const data = await apiGet<Skill[]>(`${url}${query ? '?' + query : ''}`);
      setSkills(data);
    } catch (e) {
      console.error('Failed to fetch skills', e);
    } finally {
      setLoading(false);
    }
  }, [search, roleFilter, activeTag]);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  useEffect(() => {
    apiGet<string[]>('/api/skills/tags').then(setAllTags).catch(() => {});
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await apiPost<{ synced_count: number; added: string[]; updated: string[]; removed: string[] }>('/api/skills/sync');
      setSyncResult(`Synced ${result.synced_count} — +${result.added.length} ~${result.updated.length} -${result.removed.length}`);
      fetchSkills();
    } catch (e) {
      setSyncResult('Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const handleDetail = async (name: string) => {
    try {
      const data = await apiGet<Skill>(`/api/skills/${name}`);
      setDetail(data);
    } catch (e) {
      console.error('Failed to fetch skill detail', e);
    }
  };

  return (
    <div className="skills-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="skills-panel glass">
        {/* Header */}
        <div className="skills-panel-header">
          <div className="header-left">
            <span className="panel-title">⬡ SKILLS REGISTRY</span>
            <span className="skill-count">{skills.length}</span>
          </div>
          <div className="skills-header-actions">
            <button className="action-btn-mini" onClick={handleSync} disabled={syncing}>
              {syncing ? '⟳ SYNCING...' : '⟳ SYNC'}
            </button>
            <button className="action-btn-mini" onClick={onClose}>✕</button>
          </div>
        </div>

        {syncResult && <div className="sync-result">{syncResult}</div>}

        {/* Filters */}
        <div className="skills-filters">
          <input
            className="skills-search"
            placeholder="Search skills..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="skills-role-select"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="">All roles</option>
            <option value="engineer">Engineer</option>
            <option value="architect">Architect</option>
            <option value="qa">QA</option>
            <option value="manager">Manager</option>
          </select>
        </div>

        {/* Tags */}
        {allTags.length > 0 && (
          <div className="skills-tag-bar">
            {allTags.map((t) => (
              <button
                key={t}
                className={`skill-tag-filter ${activeTag === t ? 'active' : ''}`}
                onClick={() => setActiveTag(activeTag === t ? null : t)}
              >
                {t}
              </button>
            ))}
          </div>
        )}

        {/* Grid */}
        <div className="skills-grid">
          {loading ? (
            <div className="skills-loading">Loading skills...</div>
          ) : skills.length === 0 ? (
            <div className="skills-empty">No skills found</div>
          ) : (
            skills.map((skill) => (
              <SkillCard
                key={skill.name}
                name={skill.name}
                description={skill.description}
                tags={skill.tags}
                trustLevel={skill.trust_level}
                source={skill.source}
                onClick={() => handleDetail(skill.name)}
              />
            ))
          )}
        </div>

        {/* Detail Drawer */}
        {detail && (
          <div className="skill-detail-drawer">
            <div className="skill-detail-header">
              <span className="skill-detail-name">{detail.name}</span>
              <button className="action-btn-mini" onClick={() => setDetail(null)}>✕</button>
            </div>
            <p className="skill-detail-desc">{detail.description}</p>
            <div className="skill-detail-meta">
              <span className="meta-item"><span className="meta-key">Trust:</span> <span className="meta-val">{detail.trust_level}</span></span>
              <span className="meta-item"><span className="meta-key">Source:</span> <span className="meta-val">{detail.source}</span></span>
              {detail.path && <span className="meta-item"><span className="meta-key">Path:</span> <span className="meta-val">{detail.path}</span></span>}
            </div>
            {detail.content && (
              <pre className="skill-detail-content">{detail.content}</pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
