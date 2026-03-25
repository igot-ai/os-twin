import React from "react";
import { Button } from "./Button";

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: string;
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg" | "icon";
  isLoading?: boolean;
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ icon, size = "icon", className = "", ...props }, ref) => {
    return (
      <Button ref={ref} size={size} className={className} {...props}>
        <span className="material-symbols-outlined text-[1.2rem]">{icon}</span>
      </Button>
    );
  }
);

IconButton.displayName = "IconButton";
