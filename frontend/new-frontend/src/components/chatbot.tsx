import { useEffect, useRef, useState } from "react";
import { requestChatReply } from "@/lib/chat-api";

type Msg = { id: number; sender: "user" | "bot"; text: string };

export default function Chatbot() {
  const [messages, setMessages] = useState<Msg[]>([
    { id: 1, sender: "bot", text: "Hello! How can I help today?" },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
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
      const reply = await requestChatReply(text);
      setMessages((prev) => [
        ...prev,
        { id: Date.now(), sender: "bot", text: reply },
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
    <div className="h-full w-full flex flex-col">
      <div className="flex-1 min-h-0 mx-auto w-full max-w-4xl p-4">
        <div className="h-full bg-card text-card-foreground border border-border rounded-xl shadow-lg flex flex-col">
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`max-w-[80%] p-2 rounded-2xl text-sm shadow
                  ${m.sender === "bot"
                    ? "bg-muted text-foreground self-start"
                    : "bg-primary text-primary-foreground self-end ml-auto"}`}
              >
                {m.text}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="border-t border-border p-3 flex gap-2 bg-background/60 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <input
              className="flex-1 bg-background text-foreground placeholder:text-muted-foreground border border-border rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..."
              onKeyDown={(e) => e.key === "Enter" && (void handleSend())}
              disabled={isSending}
            />
            <button
              className="px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground font-medium disabled:opacity-50"
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
