import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  activePlanId: string | null;
  setActivePlanId: (id: string | null) => void;
  theme: 'light' | 'dark';
  toggleTheme: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
  helpModalOpen: boolean;
  setHelpModalOpen: (open: boolean) => void;
  searchModalOpen: boolean;
  setSearchModalOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      activePlanId: null,
      setActivePlanId: (id) => set({ activePlanId: id }),
      theme: 'light',
      toggleTheme: () => set((s) => {
        const nextTheme = s.theme === 'light' ? 'dark' : 'light';
        if (typeof window !== 'undefined') {
          document.documentElement.setAttribute('data-theme', nextTheme);
        }
        return { theme: nextTheme };
      }),
      setTheme: (theme) => {
        if (typeof window !== 'undefined') {
          document.documentElement.setAttribute('data-theme', theme);
        }
        set({ theme });
      },
      helpModalOpen: false,
      setHelpModalOpen: (open) => set({ helpModalOpen: open }),
      searchModalOpen: false,
      setSearchModalOpen: (open) => set({ searchModalOpen: open }),
    }),
    {
      name: 'ui-storage',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        theme: state.theme,
      }),
    }
  )
);
