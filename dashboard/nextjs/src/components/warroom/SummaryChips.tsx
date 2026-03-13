'use client';

interface SummaryChipsProps {
  pending: number;
  eng: number;
  qa: number;
  passed: number;
  failed: number;
}

export default function SummaryChips({
  pending,
  eng,
  qa,
  passed,
  failed,
}: SummaryChipsProps) {
  return (
    <div className="summary-chips">
      <span className="summary-chip chip-pending">
        pending: <span>{pending}</span>
      </span>
      <span className="summary-chip chip-eng">
        eng: <span>{eng}</span>
      </span>
      <span className="summary-chip chip-qa">
        qa: <span>{qa}</span>
      </span>
      <span className="summary-chip chip-passed">
        passed: <span>{passed}</span>
      </span>
      <span className="summary-chip chip-failed">
        failed: <span>{failed}</span>
      </span>
    </div>
  );
}
