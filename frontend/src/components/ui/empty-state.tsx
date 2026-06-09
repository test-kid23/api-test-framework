import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { type LucideIcon, Inbox, Plus } from "lucide-react";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    icon?: LucideIcon;
  };
  className?: string;
  size?: "sm" | "md" | "lg";
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
  size = "md",
}: EmptyStateProps) {
  const sizeClasses = {
    sm: "p-8 text-sm",
    md: "p-12 text-base",
    lg: "p-16 text-lg",
  };

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center",
        sizeClasses[size],
        className
      )}
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-muted">
        <Icon className="h-7 w-7 text-muted-foreground" />
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-muted-foreground">{description}</p>
      )}
      {action && (
        <Button onClick={action.onClick} className="mt-4" size="sm">
          {action.icon ? (
            <action.icon className="mr-2 h-4 w-4" />
          ) : (
            <Plus className="mr-2 h-4 w-4" />
          )}
          {action.label}
        </Button>
      )}
    </div>
  );
}
