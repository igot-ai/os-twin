import React from "react";

interface TooltipProps {
  content: string;
  children: React.ReactNode;
  position?: "top" | "bottom" | "left" | "right";
  className?: string;
}

export const Tooltip = ({ content, children, position = "top", className = "" }: TooltipProps) => {
  const positions = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  return (
    <div className={`group relative inline-block ${className}`}>
      {children}
      <div
        className={`invisible group-hover:visible absolute z-[100] w-max max-w-xs rounded bg-text-main px-2 py-1 text-xs font-medium text-white shadow-lg ${positions[position]}`}
      >
        {content}
        {/* Arrow */}
        <div
          className={`absolute h-2 w-2 rotate-45 bg-text-main ${
            position === "top"
              ? "top-full left-1/2 -translate-x-1/2 -translate-y-1/2"
              : position === "bottom"
              ? "bottom-full left-1/2 -translate-x-1/2 translate-y-1/2"
              : position === "left"
              ? "left-full top-1/2 -translate-y-1/2 -translate-x-1/2"
              : "right-full top-1/2 -translate-y-1/2 translate-x-1/2"
          }`}
        />
      </div>
    </div>
  );
};
