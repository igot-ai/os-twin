'use client';


import { Modal } from './Modal';
import { useUIStore } from '@/lib/stores/uiStore';

const shortcuts = [
  { key: '⌘ + K', action: 'Open Search', category: 'Navigation' },
  { key: '?', action: 'Show Keyboard Shortcuts', category: 'Navigation' },
  { key: 'J', action: 'Select next item', category: 'Lists' },
  { key: 'K', action: 'Select previous item', category: 'Lists' },
  { key: 'Enter', action: 'Open selected item', category: 'Lists' },
  { key: 'T', action: 'Toggle Dark Mode', category: 'General' },
  { key: '[', action: 'Toggle Sidebar', category: 'General' },
];

export const KeyboardShortcutHelp = () => {
  const { helpModalOpen, setHelpModalOpen } = useUIStore();

  return (
    <Modal
      isOpen={helpModalOpen}
      onClose={() => setHelpModalOpen(false)}
      title="Keyboard Shortcuts"
      size="md"
    >
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4">
          {shortcuts.map((shortcut, index) => (
            <div
              key={index}
              className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
            >
              <span className="text-sm text-text-muted">{shortcut.action}</span>
              <div className="flex items-center gap-1">
                {shortcut.key.split(' ').map((part, i) => (
                  <kbd
                    key={i}
                    className={`
                      ${part === '+' ? 'border-0 bg-transparent shadow-none px-0.5' : 'px-1.5 py-0.5 rounded border border-border bg-background shadow-sm'}
                      text-[10px] font-mono font-bold text-text-main
                    `}
                  >
                    {part}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
        
        <div className="pt-4 text-center">
          <p className="text-[11px] text-text-faint">
            Press <kbd className="px-1 py-0.5 rounded border border-border bg-background shadow-sm text-[10px] font-mono mx-1">Esc</kbd> to close this help overlay.
          </p>
        </div>
      </div>
    </Modal>
  );
};
