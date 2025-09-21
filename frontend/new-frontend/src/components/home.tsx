import { useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { requestChatReply, type ChatResponsePayload } from "@/lib/chat-api";
import { getActiveUserId } from "@/lib/user";
import { Send, X, MessageCircle } from "lucide-react";

/**
 * Very small home dashboard with:
 *  - Events box
 *  - Calendar box (Google Calendar embed via iframe)
 *  - Minimal chat widget fixed to bottom-right
 *
 * Tailwind + shadcn/ui. Now wired to the FastAPI chat backend.
 */
export type EventItem = {
  id: string;
  title: string;
  when: string; // e.g. "Mon, Sep 22 - 10:00-11:00"
  where?: string;
};

interface HomeDashboardProps {
  /** Optional: pass a public Google Calendar embed URL. */
  calendarEmbedUrl?: string;
  /** Optional: events to show in the Events box */
  events?: EventItem[];
}

const DEFAULT_CAL_EMBED =
  "https://calendar.google.com/calendar/embed?src=c_en.basic%40group.v.calendar.google.com&ctz=UTC";

const sampleEvents: EventItem[] = [
  { id: "1", title: "Team standup", when: "Mon, Sep 22 - 10:00-10:15", where: "Meet" },
  { id: "2", title: "Design review", when: "Tue, Sep 23 - 13:00-14:00", where: "Room A" },
  { id: "3", title: "1:1 Catch-up", when: "Wed, Sep 24 - 09:30-10:00" },
];

export default function HomeDashboard({
  calendarEmbedUrl,
  events = sampleEvents,
}: HomeDashboardProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-muted/30 to-background">
      {/* Main grid */}
      <div className="mx-auto max-w-6xl p-4 md:p-8">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Events */}
          <Card className="rounded-2xl shadow-sm bg-card text-card-foreground">
            <CardHeader>
              <CardTitle className="text-xl">Upcoming Events</CardTitle>
            </CardHeader>
            <CardContent>
              {events.length === 0 ? (
                <p className="text-sm text-muted-foreground">No events to show.</p>
              ) : (
                <ul className="space-y-3">
                  {events.map((ev) => (
                    <li
                      key={ev.id}
                      className="rounded-xl border bg-muted p-3 hover:bg-accent"
                    >
                      <div className="font-medium text-card-foreground">{ev.title}</div>
                      <div className="text-sm text-muted-foreground">{ev.when}</div>
                      {ev.where && (
                        <div className="text-xs text-muted-foreground">{ev.where}</div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* Calendar */}
          <Card className="rounded-2xl shadow-sm bg-card text-card-foreground">
            <CardHeader>
              <CardTitle className="text-xl">Calendar</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="aspect-[4/3] w-full overflow-hidden rounded-xl border bg-card">
                <iframe
                  title="Google Calendar"
                  src={calendarEmbedUrl || DEFAULT_CAL_EMBED}
                  className="h-full w-full dark:invert dark:hue-rotate-180 dark:brightness-90 dark:contrast-110"
                  frameBorder="0"
                  scrolling="no"
                />
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Tip: pass a public Google Calendar embed URL via <code>calendarEmbedUrl</code>.
                In Google Calendar: Settings &gt; Select a calendar &gt; Integrate calendar &gt; "Public URL to this calendar".
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Chat widget wired to backend */}
      <ChatWidget />
    </div>
  );
}

type ChatMessage = { role: "user" | "bot"; text: string };

function formatChatReply(response: ChatResponsePayload): string {
  const pieces: string[] = [response.message];

  if (response.requires_confirmation) {
    pieces.push("The agent needs your confirmation to finish this request.");
  }

  if (response.suggestions?.length) {
    pieces.push(`Suggestions: ${response.suggestions.join(", ")}`);
  }

  if (!response.success) {
    pieces.push("The agent reported a problem while processing your request.");
  }

  return pieces.filter(Boolean).join("\n\n");
}

function ChatWidget() {
  const [isOpen, setIsOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "bot", text: "Hi! Ask me anything about your schedule." },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const listRef = useRef<HTMLDivElement | null>(null);

  const canSend = useMemo(() => input.trim().length > 0 && !isSending, [input, isSending]);

  useEffect(() => {
    const el = listRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isSending) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setIsSending(true);

    try {
      const response = await requestChatReply({
        message: text,
        conversationId,
        userId: getActiveUserId(),
      });

      setConversationId(response.conversation_id);

      const replyText = formatChatReply(response);
      setMessages((prev) => [...prev, { role: "bot", text: replyText }]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Chat request failed.";
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: `Error: ${message}` },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  if (!isOpen) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          onClick={() => setIsOpen(true)}
          className="rounded-full shadow-lg"
          size="icon"
          aria-label="Open chat"
        >
          <MessageCircle className="h-5 w-5" />
        </Button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 sm:w-96">
      <Card className="rounded-2xl shadow-lg bg-card text-card-foreground">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-base">Chat</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Close chat"
            onClick={() => setIsOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <ScrollArea className="h-56 rounded-xl border bg-background">
            <div ref={listRef} className="p-3 space-y-2 h-full overflow-y-auto">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={
                    "max-w-[85%] rounded-2xl px-3 py-2 text-sm " +
                    (m.role === "user"
                      ? "ml-auto bg-primary text-primary-foreground"
                      : "bg-muted text-foreground")
                  }
                >
                  {m.text}
                </div>
              ))}
            </div>
          </ScrollArea>

          <div className="flex items-center gap-2">
            <Input
              placeholder="Type a message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleSend();
              }}
              disabled={isSending}
            />
            <Button type="button" onClick={() => void handleSend()} disabled={!canSend}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
