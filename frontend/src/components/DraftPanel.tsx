"use client";

import { useEffect, useRef, useState } from "react";
import type { Status } from "@/lib/api";
import { Icon } from "./Icons";

type SaveState = "saved" | "dirty" | "saving";

export default function DraftPanel({
  draft,
  replyTo,
  status,
  onSave,
  onSend,
  onIgnore,
  onRedraft,
}: {
  draft: string;
  replyTo: string;
  status: Status;
  onSave: (body: string) => Promise<void>;
  onSend: (body: string, to: string) => Promise<void>;
  onIgnore: () => Promise<void>;
  onRedraft: () => Promise<void>;
}) {
  const [body, setBody] = useState(draft);
  const [to, setTo] = useState(replyTo);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);
  const [redrafting, setRedrafting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Reset when switching threads.
  useEffect(() => {
    setBody(draft);
    setSaveState("saved");
    setConfirming(false);
    setError(null);
  }, [draft]);

  useEffect(() => {
    setTo(replyTo);
  }, [replyTo]);

  // Keyboard: "e" (from the list) focuses the editor; ⌘/Ctrl+↵ opens the send
  // confirm, again to confirm; Esc backs out. Sending stays a two-step act.
  useEffect(() => {
    const focusDraft = () => textareaRef.current?.focus();
    const onKey = (ev: KeyboardEvent) => {
      if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
        if (status === "sent" || !body.trim() || sending) return;
        ev.preventDefault();
        if (confirming) void handleSend();
        else setConfirming(true);
      } else if (ev.key === "Escape" && confirming) {
        ev.preventDefault(); // claim it — page-level Esc closes the thread
        setConfirming(false);
      }
    };
    window.addEventListener("ip-focus-draft", focusDraft);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("ip-focus-draft", focusDraft);
      window.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [body, confirming, sending, status]);

  const scheduleSave = (next: string) => {
    setBody(next);
    setSaveState("dirty");
    setConfirming(false);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      setSaveState("saving");
      try {
        await onSave(next);
        setSaveState("saved");
      } catch (e) {
        setSaveState("dirty");
        setError(e instanceof Error ? e.message : "Save failed");
      }
    }, 700);
  };

  const handleRedraft = async () => {
    setRedrafting(true);
    setError(null);
    try {
      await onRedraft();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Re-draft failed");
    } finally {
      setRedrafting(false);
    }
  };

  const handleSend = async () => {
    setSending(true);
    setError(null);
    try {
      await onSend(body, to.trim());
      setConfirming(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send failed");
    } finally {
      setSending(false);
    }
  };

  if (status === "sent") {
    return (
      <div className="glass border-t border-hairline px-6 py-4">
        <p className="flex items-center gap-2 text-[13px] text-green">
          <Icon.check size={15} />
          Reply sent. It&apos;s in your Sent folder and threaded with the conversation.
        </p>
        {body && (
          <div className="email-body mt-3 max-h-40 overflow-y-auto text-[0.875rem] text-faint">
            {body}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="glass border-t border-hairline">
      <header className="flex items-center justify-between gap-3 px-6 pb-1.5 pt-3">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <span className="chip shrink-0 border-amber-dim/60 text-amber">
            {status === "drafted" ? "AI draft" : "Your reply"}
          </span>
          <span className="flex min-w-0 flex-1 items-center gap-1">
            <Icon.arrow size={11} className="shrink-0 text-faint" />
            <input
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="recipient@email.com"
              spellCheck={false}
              className="min-w-0 flex-1 bg-transparent font-mono text-[10.5px] text-muted placeholder:text-faint focus:text-ink focus:outline-none"
              title="Who this reply goes to — edit for forwarded threads"
            />
          </span>
        </div>
        <span
          className={`shrink-0 font-mono text-[10px] ${
            saveState === "saved" ? "text-faint" : saveState === "saving" ? "text-blue" : "text-amber"
          }`}
        >
          {saveState === "saved" ? "saved" : saveState === "saving" ? "saving…" : "unsaved"}
        </span>
      </header>

      <div className="px-6 pb-4">
        <textarea
          ref={textareaRef}
          value={body}
          onChange={(e) => scheduleSave(e.target.value)}
          placeholder="No draft yet — write your reply, or run Sync to have one generated."
          rows={Math.min(14, Math.max(6, body.split("\n").length + 1))}
          className="draft-editor w-full rounded-lg border border-hairline bg-base/60 px-4 py-3 text-ink placeholder:text-faint focus:border-amber-dim"
        />

        {error && <p className="mt-1.5 text-xs text-red">{error}</p>}

        <div className="mt-2.5 flex items-center justify-between">
          <div className="flex items-center gap-1">
            <button
              onClick={handleRedraft}
              disabled={redrafting}
              className="btn btn-ghost px-2 py-1 font-mono text-[11px]"
              title="Generate a fresh AI draft for this thread"
            >
              {redrafting ? "drafting…" : body.trim() ? "re-draft" : "draft with AI"}
            </button>
            <button
              onClick={onIgnore}
              className="btn btn-ghost px-2 py-1 font-mono text-[11px]"
              title="Mark this thread as not needing a reply"
            >
              ignore thread
            </button>
          </div>

          {/* Send: explicit, two-step, unmissable. The ONLY path out. */}
          {!confirming ? (
            <button
              onClick={() => setConfirming(true)}
              disabled={!body.trim()}
              className="btn btn-primary px-5 py-2 text-[13px]"
            >
              <Icon.send size={13} /> Send reply
            </button>
          ) : (
            <div className="fade-up flex items-center gap-2 rounded-lg border border-amber-dim bg-amber/10 py-1.5 pl-3 pr-1.5">
              <span className="text-[12px] text-amber">
                Send to <strong>{to.trim() || "—"}</strong>?
              </span>
              <button onClick={() => setConfirming(false)} className="btn btn-ghost px-2.5 py-1 text-[12px]">
                Cancel
              </button>
              <button
                onClick={handleSend}
                disabled={sending || !to.trim()}
                className="btn btn-primary px-3.5 py-1 text-[12px]"
              >
                {sending ? "Sending…" : "Confirm send"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
