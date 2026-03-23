'use client';

interface SummaryChipsProps {
  pending: number;
  eng: number;
  qa: number;
  passed: number;
  failed: number;
}

export default function SummaryChips({ pending, eng, qa, passed, failed }: SummaryChipsProps) {
  return (
    <div className="summary-chips">
      <span className="summary-chip chip-pending">
        pending: <span id="sum-pending">{pending}</span>
      </span>
      <span className="summary-chip chip-eng">
        eng: <span id="sum-eng">{eng}</span>
      </span>
      <span className="summary-chip chip-qa">
        qa: <span id="sum-qa">{qa}</span>
      </span>
      <span className="summary-chip chip-passed">
        passed: <span id="sum-passed">{passed}</span>
      </span>
      <span className="summary-chip chip-failed">
        failed: <span id="sum-failed">{failed}</span>
      </span>
    </div>
  );
}
