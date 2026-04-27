'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Channels has been moved into Settings → Channels.
 * This page redirects automatically.
 */
export default function ChannelsRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/settings?tab=channels');
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center text-on-surface-variant">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4 mx-auto" />
        <p className="text-sm font-body">Redirecting to Settings → Channels...</p>
      </div>
    </div>
  );
}
