'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api';
import SkillCard from '@/components/shared/SkillCard';
import MarkdownContent from '@/components/shared/MarkdownContent';

interface Skill {
  name: string;
  description: string;
  tags: string[];
  trust_level: string;
  source: string;
  path?: string;
  relative_path?: string;
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
  const [availableRoles, setAvailableRoles] = useState<string[]>([]);
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
      
      // If there's a search query, use the search endpoint
      if (search.trim()) {
        url = '/api/skills/search';
        params.set('q', search.trim());
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
    // Initial data load for filters
    apiGet<string[]>('/api/skills/tags').then(setAllTags).catch(() => {});
    apiGet<string[]>('/api/skills/roles').then(setAvailableRoles).catch(() => {});
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await apiPost<{ synced_count: number; added: string[]; updated: string[]; removed: string[] }>('/api/skills/sync');
      setSyncResult(`Synced ${result.synced_count} skills (+${result.added.length} ~${result.updated.length} -${result.removed.length})`);
      setTimeout(() => setSyncResult(null), 5000);
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
          <div className="header-left" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="panel-title" style={{ fontWeight: 800, letterSpacing: '2px', color: 'var(--text)' }}>
              ⬡ <span style={{ color: 'var(--cyan)' }}>SKILLS</span> REGISTRY
            </span>
            <span className="skill-count">{skills.length}</span>
          </div>
          <div className="skills-header-actions">
            <button className="action-btn-mini" onClick={handleSync} disabled={syncing} style={{ border: '1px solid var(--green)', color: 'var(--green)' }}>
              {syncing ? '⟳ SYNCING...' : '⟳ SYNC'}
            </button>
            <button className="action-btn-mini" onClick={onClose}>✕</button>
          </div>
        </div>

        {syncResult && <div className="sync-result">{syncResult}</div>}

        {/* Filters */}
        <div className="skills-filters">
          <div style={{ position: 'relative', flex: 1 }}>
            <input
              className="skills-search"
              placeholder="Search skills semantically..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingLeft: '28px' }}
            />
            <span style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }}>🔍</span>
          </div>
          <select
            className="skills-role-select"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="">All roles</option>
            {availableRoles.map(role => (
              <option key={role} value={role}>{role.charAt(0).toUpperCase() + role.slice(1)}</option>
            ))}
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
            <div className="skills-loading">
              <div className="active-dot" style={{ display: 'inline-block', marginRight: '8px' }}></div>
              Searching neural registry...
            </div>
          ) : skills.length === 0 ? (
            <div className="skills-empty">
              No matching skills found. Try a different query or role.
            </div>
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
            <div className="skill-detail-desc">{detail.description || 'No description provided for this skill.'}</div>
            <div className="skill-detail-meta">
              <div className="meta-item">
                <span className="meta-key">Trust:</span>
                <span className="meta-val" style={{ color: detail.trust_level === 'stable' ? 'var(--green)' : detail.trust_level === 'core' ? 'var(--cyan)' : 'var(--amber)' }}>
                  {detail.trust_level}
                </span>
              </div>
              <div className="meta-item">
                <span className="meta-key">Source:</span>
                <span className="meta-val">{detail.source}</span>
              </div>
              {detail.relative_path && (
                <div className="meta-item">
                  <span className="meta-key">RelPath:</span>
                  <span className="meta-val" style={{ opacity: 0.8, fontSize: '9px' }}>{detail.relative_path}</span>
                </div>
              )}
            </div>
            <div className="skill-detail-content-wrapper">
              {detail.content ? (
                <MarkdownContent content={detail.content} />
              ) : (
                <div style={{ color: 'var(--muted)', fontStyle: 'italic', textAlign: 'center', marginTop: '40px' }}>
                  No SKILL.md content available for inspection.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
