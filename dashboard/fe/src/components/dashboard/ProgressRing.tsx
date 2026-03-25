'use client';

interface ProgressRingProps {
  value: number;
  size?: number;
  strokeWidth?: number;
  showLabel?: boolean;
}

export default function ProgressRing({ value, size = 40, strokeWidth = 3.5, showLabel = true }: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  const color = value > 70 ? 'var(--color-success)' : value > 30 ? 'var(--color-warning)' : 'var(--color-danger)';
  const bgColor = value > 70 ? 'rgba(16, 185, 129, 0.12)' : value > 30 ? 'rgba(245, 158, 11, 0.12)' : 'rgba(239, 68, 68, 0.12)';

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none"
          stroke={bgColor}
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.6s ease-out' }}
        />
      </svg>
      {showLabel && (
        <span
          className="absolute text-[9px] font-bold"
          style={{ color }}
        >
          {value}%
        </span>
      )}
    </div>
  );
}
