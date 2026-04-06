interface ConnectorIconProps {
  name: string;
  className?: string;
}

// Maps backend icon slug -> public file path under /connectors/
const iconFileMap: Record<string, string> = {
  'intercom':        '/connectors/intercom.svg',
  'obsidian':        '/connectors/obsidian.svg',
  'zendesk':         '/connectors/zendesk.svg',
  'airtable':        '/connectors/airtable.svg',
  'notion':          '/connectors/notion.svg',
  'hubspot':         '/connectors/hubspot.svg',
  'asana':           '/connectors/asana.svg',
  'microsoft_teams': '/connectors/microsoft-teams.svg',
  'outlook':         '/connectors/outlook.svg',
};

export default function ConnectorIcon({ name, className = 'w-7 h-7' }: ConnectorIconProps) {
  const src = iconFileMap[name];

  if (!src) {
    // Fallback: material symbol icon
    return (
      <span
        className={`material-symbols-outlined flex items-center justify-center ${className}`}
        style={{ fontSize: 'inherit' }}
      >
        hub
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={name}
      className={className}
      style={{ objectFit: 'contain' }}
    />
  );
}
