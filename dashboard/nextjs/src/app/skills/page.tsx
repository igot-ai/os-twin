'use client';

import { useRouter } from 'next/navigation';
import SkillsPanel from '@/components/panels/SkillsPanel';

export default function SkillsPage() {
  const router = useRouter();

  return (
    <div style={{ height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      <SkillsPanel onClose={() => router.push('/')} />
    </div>
  );
}
