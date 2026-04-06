import React from "react";
import { Badge } from "./Badge";

interface StatusBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  status: "active" | "completed" | "blocked" | "pending" | "failed" | "inactive";
  size?: "sm" | "md";
}

export const StatusBadge = ({ status, size = "sm", className = "", label: customLabel, ...props }: StatusBadgeProps & { label?: string }) => {
  const statusConfig = {
    active: {
      variant: "primary" as const,
      label: "ACTIVE",
      dotClass: "bg-primary animate-pulse",
    },
    completed: {
      variant: "success" as const,
      label: "COMPLETED",
      dotClass: "bg-success",
    },
    blocked: {
      variant: "warning" as const,
      label: "BLOCKED",
      dotClass: "bg-warning animate-pulse",
    },
    pending: {
      variant: "muted" as const,
      label: "PENDING",
      dotClass: "bg-text-muted",
    },
    failed: {
      variant: "danger" as const,
      label: "FAILED",
      dotClass: "bg-danger",
    },
    inactive: {
      variant: "muted" as const,
      label: "INACTIVE",
      dotClass: "bg-slate-300",
    },
  };

  const config = statusConfig[status];

  return (
    <Badge
      variant={config.variant}
      size={size}
      className={`gap-1.5 ${className}`}
      {...props}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotClass}`} />
      {customLabel || config.label}
    </Badge>
  );
};
