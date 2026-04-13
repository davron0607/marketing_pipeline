import { clsx } from "clsx";

type BadgeVariant = "success" | "warning" | "danger" | "info" | "default";

const variants: Record<BadgeVariant, string> = {
  success: "bg-green-100 text-green-800",
  warning: "bg-yellow-100 text-yellow-800",
  danger: "bg-red-100 text-red-800",
  info: "bg-blue-100 text-blue-800",
  default: "bg-gray-100 text-gray-800",
};

export function Badge({
  variant = "default",
  children,
}: {
  variant?: BadgeVariant;
  children: React.ReactNode;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
        variants[variant]
      )}
    >
      {children}
    </span>
  );
}

export function jobStatusBadge(status: string) {
  const map: Record<string, BadgeVariant> = {
    pending: "warning",
    running: "info",
    completed: "success",
    failed: "danger",
  };
  return <Badge variant={map[status] || "default"}>{status}</Badge>;
}
