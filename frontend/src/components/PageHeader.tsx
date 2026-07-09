/* Consistent page shell header used across Today / Ideas / Jobs / Briefing. */
import type { ReactNode } from "react";

export default function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-6 flex items-end justify-between gap-6">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1 className="display mt-1.5 text-[1.7rem] leading-snug text-ink">{title}</h1>
        {subtitle && (
          <p className="mt-1.5 max-w-2xl text-[12.5px] leading-relaxed text-muted">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}
