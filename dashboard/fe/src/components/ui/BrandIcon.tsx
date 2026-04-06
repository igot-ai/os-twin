import React from 'react';

interface BrandIconProps {
  size?: number;
  className?: string;
  accentColor?: string;
  animated?: boolean;
}

export const BrandIcon: React.FC<BrandIconProps> = ({ 
  size = 24, 
  className = '', 
  accentColor, 
  animated = false 
}) => {
  return (
    <div className={`relative flex items-center justify-center ${className}`} style={{ width: size, height: size }}>
      {animated && (
        <div 
          className="absolute inset-[-20%] rounded-full opacity-50 animate-[spin_4s_linear_infinite]"
          style={{ 
            background: `conic-gradient(from 0deg, transparent, ${accentColor || 'var(--color-primary)'}, transparent)` 
          }} 
        />
      )}
      <svg 
        width={size} 
        height={size} 
        viewBox="0 0 24 24" 
        fill={accentColor || 'var(--color-primary)'}
        xmlns="http://www.w3.org/2000/svg"
        className="relative z-10"
      >
        <path d="M12 2L2 7.5V16.5L12 22L22 16.5V7.5L12 2ZM12 4.3L19.5 8.4V15.6L12 19.7L4.5 15.6V8.4L12 4.3Z" />
        <path d="M12 7L7.5 9.5V14.5L12 17L16.5 14.5V9.5L12 7ZM12 9.2L14.5 10.6V13.4L12 14.8L9.5 13.4V10.6L12 9.2Z" />
      </svg>
    </div>
  );
};
