'use client';

import { SWRConfig } from 'swr';
import { fetcher } from '@/lib/api-client';

export const SWRProvider = ({ children }: { children: React.ReactNode }) => {
  return (
    <SWRConfig
      value={{
        fetcher,
        refreshInterval: 0,
        dedupingInterval: 2000,
        revalidateOnFocus: false,
        shouldRetryOnError: false,
      }}
    >
      {children}
    </SWRConfig>
  );
};
