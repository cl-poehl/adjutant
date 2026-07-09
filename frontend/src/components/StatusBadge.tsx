import type { Status } from "@/lib/api";

const STYLES: Record<Status, { label: string; cls: string; dot: string }> = {
  needs_reply: { label: "needs reply", cls: "text-amber border-amber-dim/70 bg-amber/10", dot: "bg-amber" },
  drafted: { label: "draft ready", cls: "text-blue border-blue/40 bg-blue/10", dot: "bg-blue" },
  sent: { label: "sent", cls: "text-green border-green/40 bg-green/10", dot: "bg-green" },
  classified: { label: "filed", cls: "text-muted border-hairline-strong bg-raised/60", dot: "bg-faint" },
  new: { label: "new", cls: "text-muted border-hairline-strong bg-raised/60", dot: "bg-faint" },
  ignored: { label: "filtered", cls: "text-faint border-hairline bg-transparent", dot: "bg-faint" },
};

export default function StatusBadge({ status }: { status: Status }) {
  const s = STYLES[status] ?? STYLES.new;
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-px font-mono text-[9.5px] uppercase tracking-wide ${s.cls}`}
    >
      <span className={`h-1 w-1 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}
