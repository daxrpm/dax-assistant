import { useEffect, useRef, useState } from "react";
import { Button } from "@heroui/react";
import { Send, Sparkles, ShieldAlert } from "lucide-react";
import { useChatSocket } from "../hooks/useChatSocket";
import { Markdown } from "../components/Markdown";
import { Modal, Badge } from "../components/ui";
import { cn } from "../lib/cn";

export function ChatPage() {
  const { messages, status, thinking, confirmation, send, respondConfirmation } =
    useChatSocket();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, thinking]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || status !== "open") return;
    send(text);
    setInput("");
  };

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-slim px-6 py-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-5">
          {messages.length === 0 && !thinking && (
            <div className="mt-20 flex flex-col items-center text-center text-muted">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-accent">
                <Sparkles size={26} />
              </div>
              <p className="text-lg font-medium text-foreground">How can I help, Dax?</p>
              <p className="mt-1 text-sm">
                Ask anything, or have me run something on your machine.
              </p>
            </div>
          )}

          {messages.map((m) => (
            <div
              key={m.id}
              className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
                  m.role === "user"
                    ? "bg-accent text-accent-foreground"
                    : "border border-separator bg-surface text-foreground",
                )}
              >
                {m.role === "assistant" ? (
                  <Markdown content={m.content} />
                ) : (
                  <span className="whitespace-pre-wrap">{m.content}</span>
                )}
              </div>
            </div>
          ))}

          {thinking && (
            <div className="flex justify-start">
              <div className="flex items-center gap-1.5 rounded-2xl border border-separator bg-surface px-4 py-3">
                <Dot /> <Dot delay="150ms" /> <Dot delay="300ms" />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="border-t border-separator px-6 py-4">
        <form onSubmit={submit} className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(e);
              }
            }}
            rows={1}
            placeholder={
              status === "open" ? "Message Dax…" : "Connecting…"
            }
            disabled={status !== "open"}
            className="max-h-40 min-h-[44px] flex-1 resize-none rounded-2xl border border-separator bg-surface px-4 py-3 text-sm outline-none placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent/30 scroll-slim"
          />
          <Button
            type="submit"
            variant="primary"
            isIconOnly
            isDisabled={status !== "open" || !input.trim()}
            className="h-11 w-11"
            aria-label="Send"
          >
            <Send size={18} />
          </Button>
        </form>
        {status !== "open" && (
          <p className="mx-auto mt-2 max-w-3xl text-xs text-warning">
            {status === "connecting" ? "Connecting to Dax…" : "Disconnected — retrying…"}
          </p>
        )}
      </div>

      {/* Tool confirmation gate */}
      <Modal
        open={confirmation !== null}
        title={
          <span className="flex items-center gap-2">
            <ShieldAlert size={20} className="text-warning" />
            Confirm action
          </span>
        }
        footer={
          confirmation && (
            <>
              <Button
                variant="tertiary"
                onPress={() => respondConfirmation(confirmation.approval_id, false)}
              >
                Deny
              </Button>
              <Button
                variant="primary"
                onPress={() => respondConfirmation(confirmation.approval_id, true)}
              >
                Approve
              </Button>
            </>
          )
        }
      >
        {confirmation && (
          <div className="flex flex-col gap-3">
            <p className="text-muted">
              Dax wants to run a tool that may change your system. Review and confirm.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Badge color="accent">{confirmation.server_name}</Badge>
              <Badge color="warning">{confirmation.tool_name}</Badge>
            </div>
            <pre className="max-h-48 overflow-auto rounded-xl bg-surface-secondary p-3 text-xs scroll-slim">
              {JSON.stringify(confirmation.arguments, null, 2)}
            </pre>
            <p className="text-xs text-muted">
              Auto-denies in {confirmation.timeout_seconds}s if not answered.
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}

function Dot({ delay = "0ms" }: { delay?: string }) {
  return (
    <span
      className="h-2 w-2 animate-bounce rounded-full bg-muted"
      style={{ animationDelay: delay }}
    />
  );
}
