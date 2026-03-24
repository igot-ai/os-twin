import React from "react";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "circle" | "rect" | "text";
}

export const Skeleton = ({ className = "", variant = "rect", ...props }: SkeletonProps) => {
  const baseStyles = "animate-pulse bg-surface-hover rounded-md";
  
  const variants = {
    circle: "rounded-full aspect-square",
    rect: "",
    text: "h-3 w-full",
  };

  const combinedClassName = `${baseStyles} ${variants[variant]} ${className}`;

  return <div className={combinedClassName} {...props} />;
};
