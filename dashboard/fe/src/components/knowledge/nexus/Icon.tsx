'use client';

import React from 'react';

interface IconProps {
  name: string;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function Icon({ name, size = 14, className, style }: IconProps) {
  return (
    <span
      className={`material-symbols-outlined ${className ?? ''}`}
      style={{ fontSize: size, ...style }}
    >
      {name}
    </span>
  );
}
