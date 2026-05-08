import React from 'react';

interface ThinkingIconProps {
  /** Visual variant: "wave" = multi-bar audio waveform, "cursor" = single pulsing cursor */
  variant?: 'wave' | 'cursor';
  /** Size preset */
  size?: 'sm' | 'md' | 'lg';
}

const sizeMap = {
  sm: { width: 28, height: 16 },
  md: { width: 40, height: 20 },
  lg: { width: 52, height: 24 },
} as const;

export function ThinkingIcon({ variant = 'wave', size = 'md' }: ThinkingIconProps) {
  if (variant === 'cursor') {
    return (
      <svg
        width="6"
        height={sizeMap[size].height}
        viewBox={`0 0 6 ${sizeMap[size].height}`}
        xmlns="http://www.w3.org/2000/svg"
        className="animate-[pulse_1s_ease-in-out_infinite]"
      >
        <rect width="6" height={sizeMap[size].height} fill="var(--color-primary)" rx="1" />
      </svg>
    );
  }

  // Wave variant — 5 bars with staggered bounce animation
  const { width, height } = sizeMap[size];
  const barCount = 5;
  const gap = 2;
  const barWidth = Math.max(1, (width - (barCount - 1) * gap) / barCount);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      xmlns="http://www.w3.org/2000/svg"
    >
      <style>
        {`
          @keyframes thinkingWave {
            0%, 100% { transform: scaleY(0.35); }
            50% { transform: scaleY(1); }
          }
          .thinking-bar {
            fill: var(--color-primary);
            transform-box: fill-box;
            transform-origin: center center;
            animation: thinkingWave 1.2s ease-in-out infinite;
          }
          .thinking-bar:nth-child(1) { animation-delay: 0s; }
          .thinking-bar:nth-child(2) { animation-delay: 0.15s; }
          .thinking-bar:nth-child(3) { animation-delay: 0.3s; }
          .thinking-bar:nth-child(4) { animation-delay: 0.45s; }
          .thinking-bar:nth-child(5) { animation-delay: 0.6s; }
        `}
      </style>
      {Array.from({ length: barCount }).map((_, i) => (
        <rect
          key={i}
          className="thinking-bar"
          x={i * (barWidth + gap)}
          y={0}
          width={barWidth}
          height={height}
          rx={barWidth / 2}
        />
      ))}
    </svg>
  );
}
