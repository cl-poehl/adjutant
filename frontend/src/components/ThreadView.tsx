"use client";

import { useState } from "react";
import type { Message } from "@/lib/api";
import { formatDate } from "@/lib/api";

/** Find where quoted history starts so we can collapse it. */
function splitQuoted(body: string): { written: string; quoted: string } {
  const lines = body.split("\n");
  let cut = lines.length;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i].trim();
    if (/^On .{5,120} wrote:$/.test(l) || /^-{2,}\s*Original Message/i.test(l)) {
      cut = i;
      break;
    }
    // A run of ">"-quoted lines also marks history.
    if (l.startsWith(">") && lines.slice(i, i + 3).every((x) => x.trim().startsWith(">"))) {
      cut = i;
      break;
    }
  }
  return {
    written: lines.slice(0, cut).join("\n").trim(),
    quoted: lines.slice(cut).join("\n").trim(),
  };
}

function MessageCard({ message }: { message: Message }) {
  const [showQuoted, setShowQuoted] = useState(false);
  const { written, quoted } = splitQuoted(message.body_text);

  const who = message.is_from_me ? "You" : message.sender_name || message.sender_email;
  const initial = (who || "?").trim()[0]?.toUpperCase() ?? "?";

  return (
    <article
      className={`card fade-up px-5 py-4 ${
        message.is_from_me ? "ml-10 border-amber-dim/40 bg-amber/[0.03]" : "mr-2"
      }`}
    >
      <header className="mb-3 flex items-center gap-3">
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
            message.is_from_me ? "bg-amber/15 text-amber" : "bg-raised text-muted"
          }`}
        >
          {initial}
        </span>
        <div className="min-w-0 flex-1">
          <span className="text-[12.5px] font-semibold text-ink">{who}</span>
          {!message.is_from_me && message.sender_name && (
            <span className="ml-2 truncate font-mono text-[10.5px] text-faint">
              {message.sender_email}
            </span>
          )}
        </div>
        <time className="shrink-0 font-mono text-[10.5px] text-faint">
          {formatDate(message.date)}
        </time>
      </header>

      <div className="email-body text-ink/90">{written || message.body_text}</div>

      {quoted && written && (
        <div className="mt-3">
          <button
            onClick={() => setShowQuoted((v) => !v)}
            className="font-mono text-[10.5px] text-faint transition-colors hover:text-muted"
          >
            {showQuoted ? "− hide quoted history" : "··· show quoted history"}
          </button>
          {showQuoted && (
            <div className="email-body mt-2 border-l-2 border-hairline-strong pl-3 text-[0.85rem] text-faint">
              {quoted}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export default function ThreadView({
  subject,
  messages,
}: {
  subject: string;
  messages: Message[];
}) {
  return (
    <div className="space-y-3">
      <h1 className="display text-[1.4rem] leading-snug text-ink">{subject}</h1>
      {messages.map((m, i) => (
        <MessageCard key={i} message={m} />
      ))}
    </div>
  );
}
