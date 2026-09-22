import type { ReactNode } from "react";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
        {description && <p className="mt-1.5 text-muted-foreground">{description}</p>}
      </div>
      {actions}
    </div>
  );
}
