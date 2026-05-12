import React from 'react';
import { EffectComposer, SMAA } from '@react-three/postprocessing';

export default function PostFX() {
  return (
    <EffectComposer>
      <SMAA />
    </EffectComposer>
  );
}
