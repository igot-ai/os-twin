'use client';

export interface ProvenanceChipProps {
  source: string;
  className?: string;
}

const PROVENANCE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  default: { bg: '#f1f5f9', text: '#64748b', border: '#cbd5e1' },
  global:  { bg: '#dbeafe', text: '#1d4ed8', border: '#93c5fd' },
  plan:    { bg: '#f3e8ff', text: '#7c3aed', border: '#c4b5fd' },
  room:    { bg: '#fff7ed', text: '#c2410c', border: '#fdba74' },
  env:     { bg: '#fefce8', text: '#a16207', border: '#fde047' },
};

function getProvenanceType(source: string): string {
  if (source.startsWith('plan:')) return 'plan';
  if (source.startsWith('room:')) return 'room';
  if (source === 'env') return 'env';
  if (source === 'global') return 'global';
  return 'default';
}

export function ProvenanceChip({ source, className = '' }: ProvenanceChipProps) {
  const type = getProvenanceType(source);
  const colors = PROVENANCE_COLORS[type];

  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold border ${className}`}
      style={{
        background: colors.bg,
        color: colors.text,
        borderColor: colors.border,
      }}
    >
      {source}
    </span>
  );
}
