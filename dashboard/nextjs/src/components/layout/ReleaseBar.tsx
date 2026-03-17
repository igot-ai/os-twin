'use client';

import { useState, useCallback } from 'react';

interface ReleaseBarProps {
  content: string | null;
}

export default function ReleaseBar({ content }: ReleaseBarProps) {
  const [expanded, setExpanded] = useState(false);

  const toggleRelease = useCallback(() => {
    setExpanded((prev) => !prev);
  }, []);

  if (!content) return null;

  return (
    <footer className="release-bar" id="release-bar">
      <div className="release-header" onClick={toggleRelease}>
        <span className="release-icon">◆</span>
        <span className="release-title">RELEASE NOTES</span>
        <button className="release-toggle" onClick={toggleRelease}>
          {expanded ? '▴ collapse' : '▾ expand'}
        </button>
      </div>
      {expanded && (
        <div className="release-content" style={{ display: 'block' }}>
          <pre id="release-text">{content}</pre>
        </div>
      )}
    </footer>
  );
}
