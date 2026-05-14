export interface SimNode {
  id: string;
  name: string;
  label: string;
  score: number;
  degree: number;
  brightness: number;
  color: string;
  emissiveColor: string;
  shapeType: number;
  archetype: string;
  isHub: boolean;
  emissiveStrength: number;
  roleScale: number;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
  z?: number;
  vx?: number;
  vy?: number;
  vz?: number;
}

export interface SimLink {
  source: SimNode | string;
  target: SimNode | string;
  label: string;
  weight: number;
  color: string;
}

export interface SimulationInput {
  nodes: SimNode[];
  links: SimLink[];
}

export interface SimulationOptions {
  width?: number;
  height?: number;
  chargeStrength?: number;
  linkDistance?: number;
  alphaDecay?: number;
  alphaMin?: number;
  dimension?: '2d' | '3d';
}
