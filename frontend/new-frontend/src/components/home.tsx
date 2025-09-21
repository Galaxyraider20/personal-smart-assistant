import { useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { fetchCalendarEvents, type CalendarEventApi } from "@/lib/calendar";
import { sendChatMessage, formatChatReply } from "@/lib/chat";
import { getActiveUserId } from "@/lib/user";
import { Send, X, MessageCircle, CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";

type EventItem = {
  id: string;
  title: string;
  when: string;
  where?: string;
  description?: string;
};

type MonthMatrixCell = {
  date: Date;
  label: number;
  inMonth: boolean;
  isToday: boolean;
  hasEvents: boolean;
  isSelected: boolean;
};

const DAYS_TO_FETCH = 60;
const EVENTS_LIMIT = 6;

function toLocalKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function toDate(value: string) {
  return new Date(value);
}

function formatEvent(ev: CalendarEventApi): EventItem {
  const start = toDate(ev.start_time);
  const end = ev.end_time ? toDate(ev.end_time) : undefined;
  const startFmt = start.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const endFmt = end
    ? end.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : undefined;

  return {
    id: ev.id ?? `${ev.title}-${ev.start_time}`,
    title: ev.title,
    when: endFmt ? `${startFmt} - ${endFmt}` : startFmt,
    where: ev.location ?? undefined,
    description: ev.description ?? undefined,
  };
}

function buildMonthMatrix(current: Date, eventsByDay: Map<string, EventItem[]>, selectedIso: string): MonthMatrixCell[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const first = new Date(current.getFullYear(), current.getMonth(), 1);
  const startDay = first.getDay();
  const startDate = new Date(first);
  startDate.setDate(first.getDate() - startDay);

  return Array.from({ length: 42 }, (_, i) => {
    const day = new Date(startDate);
    day.setDate(startDate.getDate() + i);
    day.setHours(0, 0, 0, 0);
    const key = toLocalKey(day);

    return {
      date: day,
      label: day.getDate(),
      inMonth: day.getMonth() === current.getMonth(),
      isToday: day.getTime() === today.getTime(),
      hasEvents: eventsByDay.has(key),
      isSelected: key === selectedIso,
    };
  });
}

export default function HomeDashboard() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [eventsByDay, setEventsByDay] = useState<Map<string, EventItem[]>>(new Map());
  const [monthCells, setMonthCells] = useState<MonthMatrixCell[]>([]);
  const [viewDate, setViewDate] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return toLocalKey(today);
  });
  const [selectedEvents, setSelectedEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadEvents() {
      setLoading(true);
      setError(null);

      try {
        const now = new Date();
        const start = new Date(now);
        const end = new Date(now);
        start.setHours(0, 0, 0, 0);
        end.setDate(end.getDate() + DAYS_TO_FETCH);

        const response = await fetchCalendarEvents({ start, end, signal: controller.signal });
        const sorted = [...response.events].sort((a, b) =>
          toDate(a.start_time).getTime() - toDate(b.start_time).getTime()
        );

        const map = new Map<string, EventItem[]>();
        sorted.forEach((ev) => {
          const key = toLocalKey(toDate(ev.start_time));
          const list = map.get(key) ?? [];
          list.push(formatEvent(ev));
          map.set(key, list);
        });

        setEvents(sorted.slice(0, EVENTS_LIMIT).map(formatEvent));
        setEventsByDay(map);
      } catch (err) {
        if (controller.signal.aborted) return;
        const message = err instanceof Error ? err.message : "Unable to load events.";
        setError(message);
        setEvents([]);
        setEventsByDay(new Map());
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadEvents();
    return () => controller.abort();
  }, [viewDate]);

  useEffect(() => {
    setMonthCells(buildMonthMatrix(viewDate, eventsByDay, selectedDate));
    setSelectedEvents(eventsByDay.get(selectedDate) ?? []);
  }, [eventsByDay, viewDate, selectedDate]);

  useEffect(() => {
    setMonthCells(buildMonthMatrix(viewDate, eventsByDay, selectedDate));
    setSelectedEvents(eventsByDay.get(selectedDate) ?? []);
  }, [eventsByDay, viewDate, selectedDate]);

  const monthLabel = viewDate.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  function changeMonth(offset: number) {
    setViewDate((prev) => {
      const next = new Date(prev);
      next.setMonth(prev.getMonth() + offset);
      return next;
    });
  }

  function handleSelect(date: Date) {
    const normalized = new Date(date);
    normalized.setHours(0, 0, 0, 0);
    const iso = toLocalKey(normalized);
    setSelectedDate(iso);
    setSelectedEvents(eventsByDay.get(iso) ?? []);
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-muted/30 to-background">
      <div className="mx-auto max-w-6xl p-4 md:p-8">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <UpcomingEventsCard events={events} loading={loading} error={error} />
          <MiniCalendarCard
            monthLabel={monthLabel}
            grid={monthCells}
            loading={loading}
            error={error}
            selectedDate={selectedDate}
            selectedEvents={selectedEvents}
            onPrev={() => changeMonth(-1)}
            onNext={() => changeMonth(1)}
            onSelect={handleSelect}
          />
        </div>
      </div>

      <ChatWidget />
    </div>
  );
}

type UpcomingEventsCardProps = {
  events: EventItem[];
  loading: boolean;
  error: string | null;
};

function UpcomingEventsCard({ events, loading, error }: UpcomingEventsCardProps) {
  return (
    <Card className="rounded-2xl shadow-md bg-card text-card-foreground">
      <CardHeader>
        <CardTitle className="text-xl">Upcoming Events</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading your calendar...</p>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No upcoming events.</p>
        ) : (
          <ul className="space-y-3">
            {events.map((ev) => (
              <li
                key={ev.id}
                className="group relative rounded-xl border bg-muted/70 p-3 hover:bg-accent transition-colors"
              >
                <div className="font-medium text-card-foreground">{ev.title}</div>
                <div className="text-sm text-muted-foreground">{ev.when}</div>
                {ev.where && (
                  <div className="text-xs text-muted-foreground">{ev.where}</div>
                )}
                {ev.description && (
                  <div className="pointer-events-none absolute left-1/2 top-full z-10 hidden w-64 -translate-x-1/2 translate-y-2 rounded-xl border border-white/10 bg-slate-900/95 px-3 py-2 text-xs text-slate-100 shadow-lg group-hover:block">
                    {ev.description}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

type MiniCalendarCardProps = {
  monthLabel: string;
  grid: MonthMatrixCell[];
  loading: boolean;
  error: string | null;
  selectedDate: string;
  selectedEvents: EventItem[];
  onPrev: () => void;
  onNext: () => void;
  onSelect: (date: Date) => void;
};

function MiniCalendarCard({ monthLabel, grid, loading, error, selectedDate, selectedEvents, onPrev, onNext, onSelect }: MiniCalendarCardProps) {
  const weekdayLabels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const selectedLabel = new Date(selectedDate).toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });

  return (
    <Card className="rounded-2xl shadow-md bg-card text-card-foreground">
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays className="h-5 w-5" />
          <div>
            <CardTitle className="text-xl leading-tight">{monthLabel}</CardTitle>
            <p className="text-xs text-muted-foreground">{selectedLabel}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Previous month" onClick={onPrev}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Next month" onClick={onNext}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <p className="text-sm text-muted-foreground">Syncing your calendar...</p>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : (
          <>
            <div className="grid grid-cols-7 text-xs uppercase tracking-wide text-muted-foreground text-center">
              {weekdayLabels.map((label) => (
                <div key={label} className="py-1 font-medium">
                  {label}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-1">
              {grid.map((cell, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => onSelect(cell.date)}
                  className={[
                    "aspect-square rounded-lg flex items-center justify-center text-sm transition-colors",
                    cell.inMonth ? "text-card-foreground" : "text-muted-foreground/50",
                    cell.hasEvents && cell.inMonth ? "border border-primary/70 bg-primary/10" : "border border-border/60",
                    cell.isToday ? "ring-2 ring-primary" : "",
                    cell.isSelected ? "bg-primary text-primary-foreground" : "",
                  ].filter(Boolean).join(" ")}
                >
                  <span className="relative">
                    {cell.label}
                    {cell.hasEvents && !cell.isSelected && (
                      <span className="absolute -bottom-1 left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-primary"></span>
                    )}
                  </span>
                </button>
              ))}
            </div>
            {selectedEvents.length > 0 && (
              <div className="mt-2 space-y-2 text-xs">
                {selectedEvents.map((item) => (
                  <div key={item.id} className="rounded-md border border-border/60 bg-muted/70 px-2 py-1">
                    <div className="font-medium text-card-foreground text-sm">{item.title}</div>
                    <div className="text-muted-foreground">{item.when}</div>
                    {item.where && (
                      <div className="text-muted-foreground">{item.where}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

type ChatMessage = { role: "user" | "bot"; text: string };

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
      const response = await sendChatMessage({
        message: text,
        conversationId,
        userId: getActiveUserId() || "anonymous",
      });

      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }

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
      <Card className="rounded-2xl shadow-xl bg-card/95 text-card-foreground backdrop-blur">
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
          <ScrollArea className="h-56 rounded-xl border bg-background/80">
            <div ref={listRef} className="p-3 space-y-2 h-full overflow-y-auto">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={
                    "max-w-[85%] rounded-2xl px-3 py-2 text-sm shadow-sm " +
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
