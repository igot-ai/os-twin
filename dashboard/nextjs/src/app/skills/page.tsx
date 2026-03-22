'use client';

import { useRouter } from 'next/navigation';
import SkillsPanel from '@/components/panels/SkillsPanel';

export default function SkillsPage() {
  const router = useRouter();
  
  return (
    <div style={{ width: '100vw', height: '100vh', background: 'var(--bg)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      <SkillsPanel onClose={() => router.push('/')} />
    </div>
  );
}
