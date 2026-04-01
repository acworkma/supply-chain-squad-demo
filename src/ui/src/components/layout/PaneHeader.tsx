import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface PaneHeaderProps {
  icon: LucideIcon;
  title: string;
  badge?: string | number;
  badgeVariant?: "default" | "warning" | "error" | "success";
  className?: string;
}

const badgeColors: Record<string, string> = {
  default: "bg-tower-accent/20 text-tower-accent",
  warning: "bg-tower-warning/20 text-tower-warning",
  error: "bg-tower-error/20 text-tower-error",
  success: "bg-tower-success/20 text-tower-success",
};

export function PaneHeader({
  icon: Icon,
  title,
  badge,
  badgeVariant = "default",
  className,
}: PaneHeaderProps) {
  return (
    <div
      className={cn(
        "relative flex items-center gap-2.5 px-4 py-3 border-b border-tower-border",
        className
      )}
    >
      {/* Accent highlight bar */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-tower-accent/40 to-transparent" />

      <Icon className="h-4 w-4 text-tower-accent shrink-0" />
      <h2 className="text-sm font-semibold tracking-wide text-gray-200 uppercase">
        {title}
      </h2>

      {badge !== undefined && (
        <span
          className={cn(
            "ml-auto inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
            badgeColors[badgeVariant]
          )}
        >
          {badge}
        </span>
      )}
    </div>
  );
}
