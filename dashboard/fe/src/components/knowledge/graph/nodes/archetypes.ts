export type Archetype = 'hub' | 'authority' | 'authority-featured' | 'transient' | 'peripheral' | 'structural' | 'fragment';

export const LABEL_ARCHETYPES: Record<string, Archetype> = {
  text_chunk: 'fragment',
  person: 'authority',
  organization: 'authority-featured',
  entity: 'authority',
  concept: 'structural',
  technology: 'structural',
  law: 'structural',
  document: 'transient',
  media: 'transient',
  location: 'peripheral',
  city: 'peripheral',
  country: 'peripheral',
  date: 'peripheral',
  money: 'peripheral',
  event: 'authority',
  group: 'authority',
};

export const ARCHETYPE_EMISSIVE_STRENGTH: Record<Archetype, number> = {
  hub: 1.5,
  authority: 0.5,
  'authority-featured': 0.6,
  transient: 0.45,
  peripheral: 0.15,
  structural: 0.7,
  fragment: 0.1,
};

export const ARCHETYPE_SCALE: Record<Archetype, number> = {
  hub: 2.4,
  authority: 1.0,
  'authority-featured': 1.0,
  transient: 0.85,
  peripheral: 0.6,
  structural: 0.9,
  fragment: 0.4,
};

export function getArchetype(label: string): Archetype {
  return LABEL_ARCHETYPES[label.toLowerCase()] ?? 'authority';
}

export function isHubArchetype(degree: number, allDegrees: number[]): boolean {
  if (allDegrees.length < 5) return false;
  const sorted = [...allDegrees].sort((a, b) => b - a);
  const top5PctIndex = Math.max(0, Math.floor(sorted.length * 0.05) - 1);
  return degree >= sorted[top5PctIndex] && degree > 0;
}
