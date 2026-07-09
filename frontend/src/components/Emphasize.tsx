import React from "react";

/* Renders model-authored emphasis. The LLM decides what carries weight and
   marks it inline; we just style those marks. Nothing is detected or guessed
   client-side.

   • ==phrase==  → bold + highlighted  (the most decision-driving phrase)
   • **phrase**  → bold                (secondary key terms)                */

const RE = /==([^=\n]+)==|\*\*([^*\n]+)\*\*/g;

export function emphasize(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  RE.lastIndex = 0;
  while ((m = RE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const highlight = m[1];
    const bold = m[2];
    if (highlight !== undefined) {
      out.push(
        <mark key={key++} className="mark">
          {highlight}
        </mark>,
      );
    } else {
      out.push(
        <strong key={key++} className="strong">
          {bold}
        </strong>,
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Render a string with the model's inline emphasis. Non-strings pass through. */
export default function Emphasize({ children }: { children: React.ReactNode }) {
  if (typeof children !== "string") return <>{children}</>;
  return <>{emphasize(children)}</>;
}
