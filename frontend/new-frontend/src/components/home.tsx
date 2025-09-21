import React, { useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, X, MessageCircle } from "lucide-react";

/**
 * Very small home dashboard with:
 *  - Events box
 *  - Calendar box (Google Calendar embed via iframe)
 *  - Minimal chat widget fixed to bottom-right
 *
 * Tailwind + shadcn/ui. No networking by default.
 */
export type EventItem = {
  id: string;
  title: string;
  when: string; // e.g. "Mon, Sep 22 • 10:00–11:00"
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
  { id: "1", title: "Team standup", when: "Mon, Sep 22 • 10:00–10:15", where: "Meet" },
  { id: "2", title: "Design review", when: "Tue, Sep 23 • 13:00–14:00", where: "Room A" },
  { id: "3", title: "1:1 Catch-up", when: "Wed, Sep 24 • 09:30–10:00" },
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
                In Google Calendar: Settings → Select a calendar → Integrate calendar → "Public URL to this calendar".
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Chat widget (local state only) */}
      <ChatWidget />
    </div>
  );
}

function ChatWidget() {
  const [isOpen, setIsOpen] = useState(true);
  const [messages, setMessages] = useState<{ role: "user" | "bot"; text: string }[]>([
    { role: "bot", text: "Hi! This is a local demo chat. Type below." },
  ]);
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  const canSend = useMemo(() => input.trim().length > 0, [input]);

  function handleSend() {
    if (!canSend) return;
    const text = input.trim();
    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", text },
      { role: "bot", text: `Echo: ${text}` },
    ]);
    setTimeout(
      () => listRef.current?.scrollTo({
        top: listRef.current.scrollHeight,
        behavior: "smooth",
      }),
      0
    );
  }

  // When closed, show a small floating button to reopen
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
              placeholder="Type a message…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSend();
              }}
            />
            <Button type="button" onClick={handleSend} disabled={!canSend}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
