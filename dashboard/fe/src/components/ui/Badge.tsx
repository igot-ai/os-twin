import React from "react";

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "primary" | "secondary" | "outline" | "success" | "warning" | "danger" | "muted";
  size?: "sm" | "md";
}

export const Badge = ({ className = "", variant = "primary", size = "sm", children, ...props }: BadgeProps) => {
  const baseStyles = "inline-flex items-center rounded-full font-bold border transition-colors";
  
  const variants = {
    primary: "bg-primary-muted text-primary border-primary/20",
    secondary: "bg-surface text-text-main border-border",
    outline: "bg-transparent text-text-main border-border",
    success: "bg-success-light text-success-text border-success/20",
    warning: "bg-warning-light text-warning-text border-warning/20",
    danger: "bg-danger-light text-danger-text border-danger/20",
    muted: "bg-surface-hover text-text-muted border-border",
  };

  const sizes = {
    sm: "px-2 py-0.5 text-[10px]",
    md: "px-2.5 py-1 text-xs",
  };

  const combinedClassName = `${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`;

  return (
    <div className={combinedClassName} {...props}>
      {children}
    </div>
  );
};
