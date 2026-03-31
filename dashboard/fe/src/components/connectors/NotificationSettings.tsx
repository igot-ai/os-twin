'use client';

const AVAILABLE_EVENTS = [
  'room_created',
  'room_updated',
  'room_removed',
  'room_message',
  'plans_updated',
  'reaction_toggled',
  'comment_published',
  'error',
  'escalation',
  'alert',
  'done',
];

function formatEventLabel(event: string): string {
  return event
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

interface NotificationSettingsProps {
  selectedEvents: string[];
  onChange: (events: string[]) => void;
}

export function NotificationSettings({ selectedEvents, onChange }: NotificationSettingsProps) {
  const toggle = (event: string) => {
    if (selectedEvents.includes(event)) {
      onChange(selectedEvents.filter((e) => e !== event));
    } else {
      onChange([...selectedEvents, event]);
    }
  };

  const allSelected = AVAILABLE_EVENTS.every((e) => selectedEvents.includes(e));

  const toggleAll = () => {
    onChange(allSelected ? [] : [...AVAILABLE_EVENTS]);
  };

  return (
    <section
      className="rounded-xl border p-5"
      style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
    >
      <div className="flex items-center justify-between mb-4">
        <h2
          className="text-sm font-bold flex items-center gap-2"
          style={{ color: 'var(--color-text-main)' }}
        >
          <span className="material-symbols-outlined text-base">notifications</span>
          Notification Events
        </h2>
        <button
          onClick={toggleAll}
          className="text-[10px] font-semibold px-2 py-1 rounded"
          style={{ color: 'var(--color-primary)' }}
        >
          {allSelected ? 'Deselect All' : 'Select All'}
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
        {AVAILABLE_EVENTS.map((event) => {
          const checked = selectedEvents.includes(event);
          return (
            <label
              key={event}
              className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors text-xs font-medium"
              style={{
                background: checked ? 'var(--color-primary-muted)' : 'var(--color-background)',
                color: checked ? 'var(--color-primary)' : 'var(--color-text-muted)',
              }}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(event)}
                className="sr-only"
              />
              <span
                className="material-symbols-outlined text-sm"
                style={{ color: checked ? 'var(--color-primary)' : 'var(--color-text-faint)' }}
              >
                {checked ? 'check_box' : 'check_box_outline_blank'}
              </span>
              {formatEventLabel(event)}
            </label>
          );
        })}
      </div>
    </section>
  );
}
