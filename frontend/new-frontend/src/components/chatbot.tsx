import { useEffect, useRef, useState } from "react";
import { sendChatMessage, formatChatReply } from "@/lib/chat";
import { getActiveUserId } from "@/lib/user";

type Msg = { id: number; sender: "user" | "bot"; text: string };

export default function Chatbot() {
  const [messages, setMessages] = useState<Msg[]>([
    { id: 1, sender: "bot", text: "Hello! How can I help today?" },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isSending) return;

    const userMsg: Msg = { id: Date.now(), sender: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsSending(true);

    try {
      const response = await sendChatMessage({
        message: text,
        conversationId,
        userId: getActiveUserId() || "anonymous",
      });

      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }

      const replyText = formatChatReply(response);
      setMessages((prev) => [
        ...prev,
        { id: Date.now(), sender: "bot", text: replyText },
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Chat request failed.";
      setMessages((prev) => [
        ...prev,
        { id: Date.now(), sender: "bot", text: `Error: ${message}` },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-foreground">
      <div className="mx-auto max-w-5xl p-6 md:p-10 space-y-6">
        <header className="space-y-2">
          <h1 className="text-2xl md:text-3xl font-semibold text-white">Assistant Chat</h1>
          <p className="text-sm text-slate-300">Ask anything about your tasks, schedule, or notes.</p>
        </header>

        <div className="rounded-3xl border border-white/10 bg-slate-900/70 shadow-2xl backdrop-blur-xl flex flex-col h-[70vh]">
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-3">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`max-w-3xl px-4 py-3 rounded-2xl text-sm shadow-sm transition-colors tracking-wide leading-relaxed
                  ${m.sender === "bot"
                    ? "bg-slate-800/80 text-slate-100 border border-white/5"
                    : "bg-primary text-primary-foreground ml-auto"}`}
              >
                {m.text}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="border-t border-white/10 px-6 py-4 bg-slate-900/80 backdrop-blur flex gap-3">
            <input
              className="flex-1 bg-slate-950/80 text-slate-100 placeholder:text-slate-500 border border-white/10 rounded-2xl px-4 py-3 text-sm
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..."
              onKeyDown={(e) => e.key === "Enter" && (void handleSend())}
              disabled={isSending}
            />
            <button
              className="px-6 py-3 rounded-2xl bg-primary hover:bg-primary/90 text-primary-foreground font-medium disabled:opacity-50"
              onClick={() => void handleSend()}
              disabled={isSending || input.trim().length === 0}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
