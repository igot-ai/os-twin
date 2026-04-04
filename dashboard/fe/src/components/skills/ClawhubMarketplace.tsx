'use client';

import React, { useState, useEffect } from 'react';
import { useClawhubSearch, useClawhubInstalled, ClawhubSkill } from '@/hooks/use-skills';

type InstallState = {
  phase: 'installing' | 'success' | 'error';
  name: string;
  slug: string;
  msg?: string;
};

interface ClawhubMarketplaceProps {
  onInstalled?: () => void;
}

export const ClawhubMarketplace: React.FC<ClawhubMarketplaceProps> = ({ onInstalled }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [installStates, setInstallStates] = useState<Record<string, InstallState>>({});
  const [selectedSkill, setSelectedSkill] = useState<ClawhubSkill | null>(null);

  const { results, isLoading, isError, installSkill } = useClawhubSearch(debouncedSearch);
  const { installedSlugs, refresh: refreshInstalled } = useClawhubInstalled();

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const handleInstall = async (skill: ClawhubSkill) => {
    const slug = skill.slug || skill.name;
    setInstallStates((prev) => ({
      ...prev,
      [slug]: { phase: 'installing', name: skill.name, slug },
    }));
    try {
      await installSkill(slug);
      setInstallStates((prev) => ({
        ...prev,
        [slug]: { phase: 'success', name: skill.name, slug, msg: 'Installed' },
      }));
      refreshInstalled();
      onInstalled?.();
    } catch (e: any) {
      setInstallStates((prev) => ({
        ...prev,
        [slug]: { phase: 'error', name: skill.name, slug, msg: e?.message || 'Install failed' },
      }));
    }
  };

  const dismissStatus = (slug: string) => {
    setInstallStates((prev) => {
      const next = { ...prev };
      delete next[slug];
      return next;
    });
  };

  // Collect completed install banners
  const banners = Object.values(installStates).filter((s) => s.phase !== 'installing');

  return (
    <div className="space-y-4">
      {/* Search */}
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-lg max-w-md"
        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
      >
        <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-text-faint)' }}>
          travel_explore
        </span>
        <input
          type="text"
          placeholder="Search ClawhHub marketplace..."
          className="bg-transparent border-none outline-none text-xs w-full"
          style={{ color: 'var(--color-text-main)' }}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      {/* Status banners */}
      {banners.length > 0 && (
        <div className="space-y-2">
          {banners.map((s) => (
            <div
              key={s.slug}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                s.phase === 'success'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}
            >
              <span className="material-symbols-outlined text-sm">
                {s.phase === 'success' ? 'check_circle' : 'error'}
              </span>
              <span className="font-semibold">{s.name}</span> — {s.msg}
              <button onClick={() => dismissStatus(s.slug)} className="ml-auto hover:opacity-70">
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!debouncedSearch && (
        <div className="p-12 text-center border border-dashed border-border rounded-xl">
          <span className="material-symbols-outlined text-4xl mb-2" style={{ color: 'var(--color-text-faint)' }}>
            store
          </span>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Search the ClawhHub marketplace to discover and install community skills
          </p>
        </div>
      )}

      {/* Loading */}
      {debouncedSearch && isLoading && (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-36 rounded-xl bg-slate-100 animate-pulse" />
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="p-8 text-center text-red-500 text-sm">
          Failed to search ClawhHub. Make sure the service is reachable.
        </div>
      )}

      {/* Results */}
      {debouncedSearch && !isLoading && results && results.length > 0 && (
        <>
          <div className="text-[11px] font-medium" style={{ color: 'var(--color-text-faint)' }}>
            {results.length} result{results.length !== 1 ? 's' : ''} from ClawhHub
          </div>
          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}>
            {results.map((skill) => {
              const slug = skill.slug || skill.name;
              const state = installStates[slug];
              const alreadyInstalled = installedSlugs.has(slug);
              return (
                <ClawhubSkillCard
                  key={slug}
                  skill={skill}
                  installState={state}
                  alreadyInstalled={alreadyInstalled}
                  onInstall={() => handleInstall(skill)}
                  onClick={() => setSelectedSkill(skill)}
                />
              );
            })}
          </div>
        </>
      )}

      {/* No results */}
      {debouncedSearch && !isLoading && results && results.length === 0 && (
        <div className="p-12 text-center border border-dashed border-border rounded-xl">
          <span className="material-symbols-outlined text-4xl mb-2" style={{ color: 'var(--color-text-faint)' }}>
            search_off
          </span>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            No skills found on ClawhHub for &quot;{debouncedSearch}&quot;
          </p>
        </div>
      )}
      {/* Detail Modal */}
      {selectedSkill && (
        <ClawhubDetailModal
          skill={selectedSkill}
          isInstalled={installedSlugs.has(selectedSkill.slug || selectedSkill.name)}
          installState={installStates[selectedSkill.slug || selectedSkill.name]}
          onClose={() => setSelectedSkill(null)}
          onInstall={() => { handleInstall(selectedSkill); }}
        />
      )}
    </div>
  );
};

/* ─── Detail Modal ────────────────────────────────────────────────────────── */

interface ClawhubDetailModalProps {
  skill: ClawhubSkill;
  isInstalled: boolean;
  installState?: InstallState;
  onClose: () => void;
  onInstall: () => void;
}

const ClawhubDetailModal: React.FC<ClawhubDetailModalProps> = ({ skill, isInstalled, installState, onClose, onInstall }) => {
  const phase = installState?.phase;
  const installed = phase === 'success' || (!phase && isInstalled);
  const isInstalling = phase === 'installing';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto"
        style={{ background: 'var(--color-surface)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b" style={{ borderColor: 'var(--color-border)' }}>
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded text-white"
              style={{ background: '#6366f1' }}
            >
              clawhub
            </span>
            <span className="text-lg font-bold" style={{ color: 'var(--color-text-main)' }}>
              {skill.name}
            </span>
            {skill.version && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: '#f1f5f9', color: 'var(--color-text-faint)' }}>
                v{skill.version}
              </span>
            )}
            {installed && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600 border border-emerald-200">
                INSTALLED
              </span>
            )}
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-slate-100 transition-colors">
            <span className="material-symbols-outlined text-lg" style={{ color: 'var(--color-text-muted)' }}>close</span>
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {/* Slug */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase" style={{ color: 'var(--color-text-faint)' }}>Slug</span>
            <code className="text-xs px-2 py-0.5 rounded" style={{ background: '#f1f5f9', color: 'var(--color-text-main)' }}>
              {skill.slug}
            </code>
          </div>

          {/* Description */}
          <div>
            <span className="text-[10px] font-semibold uppercase block mb-1" style={{ color: 'var(--color-text-faint)' }}>Description</span>
            <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
              {skill.description || 'No description available.'}
            </p>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-4 text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
            {skill.author && (
              <span className="flex items-center gap-1">
                <span className="material-symbols-outlined text-xs">person</span>
                {skill.author}
              </span>
            )}
            {(skill.downloads != null && skill.downloads > 0) && (
              <span className="flex items-center gap-1">
                <span className="material-symbols-outlined text-xs">download</span>
                {skill.downloads.toLocaleString()} downloads
              </span>
            )}
            {(skill.installs != null && skill.installs > 0) && (
              <span className="flex items-center gap-1">
                <span className="material-symbols-outlined text-xs">install_desktop</span>
                {skill.installs.toLocaleString()} installs
              </span>
            )}
            {skill.score != null && (
              <span className="flex items-center gap-1">
                <span className="material-symbols-outlined text-xs">star</span>
                {Math.round(skill.score * 10) / 10} relevance
              </span>
            )}
          </div>

          {/* Tags */}
          {skill.tags && skill.tags.length > 0 && (
            <div>
              <span className="text-[10px] font-semibold uppercase block mb-1" style={{ color: 'var(--color-text-faint)' }}>Tags</span>
              <div className="flex flex-wrap gap-1">
                {skill.tags.map((tag) => (
                  <span key={tag} className="text-[10px] px-2 py-0.5 rounded-sm bg-indigo-50 border border-indigo-100 text-indigo-500">
                    #{tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Install command */}
          <div>
            <span className="text-[10px] font-semibold uppercase block mb-1" style={{ color: 'var(--color-text-faint)' }}>Install command</span>
            <code className="block text-xs px-3 py-2 rounded-md font-mono" style={{ background: '#1e293b', color: '#e2e8f0' }}>
              npx clawhub install {skill.slug || skill.name}
            </code>
          </div>

          {/* Installing progress */}
          {isInstalling && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-indigo-50 border border-indigo-100">
              <span className="material-symbols-outlined text-sm animate-spin text-indigo-500">progress_activity</span>
              <span className="text-xs text-indigo-600 font-medium">Installing...</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-5 border-t" style={{ borderColor: 'var(--color-border)' }}>
          <a
            href={`https://clawhub.ai/skills/${skill.slug || skill.name}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-indigo-500 hover:underline flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm">open_in_new</span>
            View on ClawhHub
          </a>
          {installed ? (
            <span className="flex items-center gap-1 px-4 py-2 rounded-lg text-xs font-semibold text-emerald-600 bg-emerald-50 border border-emerald-200">
              <span className="material-symbols-outlined text-sm">check_circle</span>
              Installed
            </span>
          ) : (
            <button
              onClick={onInstall}
              disabled={isInstalling}
              className="flex items-center gap-1 px-4 py-2 rounded-lg text-xs font-semibold text-white transition-colors disabled:opacity-50"
              style={{ background: '#6366f1' }}
            >
              <span className={`material-symbols-outlined text-sm ${isInstalling ? 'animate-spin' : ''}`}>
                {isInstalling ? 'progress_activity' : 'download'}
              </span>
              {isInstalling ? 'Installing...' : 'Install Skill'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

/* ─── Card for a ClawhHub result ──────────────────────────────────────────── */

interface ClawhubSkillCardProps {
  skill: ClawhubSkill;
  installState?: InstallState;
  alreadyInstalled?: boolean;
  onInstall: () => void;
  onClick?: () => void;
}

const ClawhubSkillCard: React.FC<ClawhubSkillCardProps> = ({ skill, installState, alreadyInstalled, onInstall, onClick }) => {
  const phase = installState?.phase;
  const isInstalling = phase === 'installing';
  const isInstalled = phase === 'success' || (!phase && alreadyInstalled);

  return (
    <div
      className="p-4 rounded-xl border transition-all duration-200 fade-in-up flex flex-col cursor-pointer"
      style={{
        borderColor: isInstalled ? '#10b981' : 'var(--color-border)',
        background: 'var(--color-surface)',
        boxShadow: 'var(--shadow-card)',
        minHeight: '150px',
      }}
      onClick={onClick}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = 'var(--shadow-card-hover)';
        e.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = 'var(--shadow-card)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded text-white"
            style={{ background: '#6366f1' }}
          >
            clawhub
          </span>
          <span className="text-sm font-bold" style={{ color: 'var(--color-text-main)' }}>
            {skill.name}
          </span>
          {skill.version && (
            <span
              className="text-[9px] font-mono px-1.5 py-0.5 rounded"
              style={{ background: '#f1f5f9', color: 'var(--color-text-faint)' }}
            >
              v{skill.version}
            </span>
          )}
        </div>
      </div>

      {/* Description */}
      <p className="text-[11px] leading-relaxed mb-3 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>
        {skill.description || 'No description available'}
      </p>

      {/* Tags */}
      {skill.tags && skill.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {skill.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="text-[9px] px-1.5 py-0.5 rounded-sm bg-indigo-50 border border-indigo-100 text-indigo-500"
            >
              #{tag}
            </span>
          ))}
          {skill.tags.length > 4 && <span className="text-[9px] text-slate-400">+{skill.tags.length - 4}</span>}
        </div>
      )}

      {/* Install progress inline */}
      {isInstalling && (
        <div className="flex items-center gap-2 mb-3 px-2 py-1.5 rounded-md bg-indigo-50 border border-indigo-100">
          <span className="material-symbols-outlined text-sm animate-spin text-indigo-500">progress_activity</span>
          <span className="text-[11px] text-indigo-600 font-medium">
            Installing <span className="font-mono">{skill.slug || skill.name}</span>...
          </span>
        </div>
      )}

      {/* Footer */}
      <div
        className="flex items-center justify-between mt-auto pt-3 border-t border-dashed"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <div className="flex items-center gap-2 text-[10px]" style={{ color: 'var(--color-text-faint)' }}>
          {skill.score != null && (
            <span className="px-1 rounded bg-yellow-50 text-yellow-700 border border-yellow-200" title="Relevance">
              {Math.round(skill.score * 10) / 10}
            </span>
          )}
          {skill.author && (
            <span className="flex items-center gap-0.5">
              <span className="material-symbols-outlined text-[10px]">person</span>
              {skill.author}
            </span>
          )}
          {(skill.downloads != null && skill.downloads > 0) && (
            <span className="flex items-center gap-0.5">
              <span className="material-symbols-outlined text-[10px]">download</span>
              {skill.downloads.toLocaleString()}
            </span>
          )}
          {(skill.installs != null && skill.installs > 0) && (
            <span className="flex items-center gap-0.5">
              <span className="material-symbols-outlined text-[10px]">install_desktop</span>
              {skill.installs.toLocaleString()}
            </span>
          )}
        </div>

        {/* Button changes based on state */}
        {isInstalled ? (
          <span className="flex items-center gap-1 px-3 py-1.5 rounded-md text-[11px] font-semibold text-emerald-600 bg-emerald-50 border border-emerald-200">
            <span className="material-symbols-outlined text-sm">check_circle</span>
            Installed
          </span>
        ) : phase === 'error' ? (
          <button
            onClick={(e) => { e.stopPropagation(); onInstall(); }}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md text-[11px] font-semibold text-white transition-colors"
            style={{ background: '#ef4444' }}
          >
            <span className="material-symbols-outlined text-sm">refresh</span>
            Retry
          </button>
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); onInstall(); }}
            disabled={isInstalling}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md text-[11px] font-semibold text-white transition-colors disabled:opacity-50"
            style={{ background: '#6366f1' }}
          >
            <span className={`material-symbols-outlined text-sm ${isInstalling ? 'animate-spin' : ''}`}>
              {isInstalling ? 'progress_activity' : 'download'}
            </span>
            {isInstalling ? 'Installing...' : 'Install'}
          </button>
        )}
      </div>
    </div>
  );
};
