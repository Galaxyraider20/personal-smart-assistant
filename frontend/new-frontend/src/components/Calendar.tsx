import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon } from "lucide-react";
import { fetchCalendarEvents } from "@/lib/calendar";

/** Calendar event type */
export type CalEvent = {
  id: string;
  title: string;
  start: Date | string;
  end?: Date | string | null;
  where?: string | null;
  description?: string | null;
  attendees?: string[];
};

interface CalendarProps {
  events?: CalEvent[];
  weekStartsOn?: 0 | 1; // 0=Sun, 1=Mon
}

/* ---------- tiny date helpers (no deps) ---------- */
function startOfDay(d: Date) { const x = new Date(d); x.setHours(0,0,0,0); return x; }
function isSameDay(a: Date, b: Date) { return startOfDay(a).getTime() === startOfDay(b).getTime(); }
function isSameMonth(a: Date, b: Date) { return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth(); }
function addDays(d: Date, n: number) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function addMonths(d: Date, n: number) { const x = new Date(d); x.setMonth(x.getMonth() + n); return x; }
function startOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function startOfWeek(d: Date, weekStartsOn: 0|1) {
  const x = startOfDay(d);
  const day = x.getDay(); // 0..6 (Sun..Sat)
  const diff = weekStartsOn === 1 ? (day === 0 ? 6 : day - 1) : day; // shift if Mon-start
  return addDays(x, -diff);
}
function formatMonthYear(d: Date) {
  return d.toLocaleString(undefined, { month: "long", year: "numeric" });
}
function ymd(d: Date) {
  const m = d.getMonth() + 1, day = d.getDate();
  return `${d.getFullYear()}-${String(m).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}
function toDate(x: Date | string) { return x instanceof Date ? x : new Date(x); }

function ensureId(id: string | null | undefined, fallbackSeed: string, index: number): string {
  if (id && id.length > 0) return id;
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `event_${index}_${fallbackSeed}`;
}

/* ---------- the component ---------- */
export default function CalendarPage({
  events: externalEvents,
  weekStartsOn = 0,
}: CalendarProps) {
  const today = startOfDay(new Date());
  const [viewDate, setViewDate] = useState<Date>(startOfMonth(today));
  const [selectedDate, setSelectedDate] = useState<Date>(today);
  const [events, setEvents] = useState<CalEvent[]>(externalEvents ?? []);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (externalEvents) {
      setEvents(externalEvents);
    }
  }, [externalEvents]);

  useEffect(() => {
    if (externalEvents) return;

    const controller = new AbortController();
    async function loadEvents() {
      setIsLoading(true);
      setError(null);
      try {
        const rangeStart = startOfWeek(startOfMonth(viewDate), weekStartsOn);
        const rangeEnd = addDays(rangeStart, 42);
        const data = await fetchCalendarEvents({ start: rangeStart, end: rangeEnd, signal: controller.signal });
        const normalized: CalEvent[] = data.events.map((ev, index) => ({
          id: ensureId(ev.id, ev.start_time, index),
          title: ev.title,
          start: ev.start_time,
          end: ev.end_time ?? undefined,
          where: ev.location ?? undefined,
          description: ev.description ?? undefined,
          attendees: ev.attendees,
        }));
        setEvents(normalized);
      } catch (err) {
        if (controller.signal.aborted) return;
        const message = err instanceof Error ? err.message : "Failed to load calendar events.";
        setError(message);
        setEvents([]);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void loadEvents();
    return () => controller.abort();
  }, [externalEvents, viewDate, weekStartsOn]);

  // Normalize + index events per day (YYYY-MM-DD)
  const eventsByDay = useMemo(() => {
    const map = new Map<string, CalEvent[]>();
    for (const ev of events) {
      const d = ymd(toDate(ev.start));
      if (!map.has(d)) map.set(d, []);
      map.get(d)!.push(ev);
    }
    return map;
  }, [events]);

  // Build a 6x7 grid starting at the week containing the 1st of the month
  const gridStart = useMemo(() => startOfWeek(startOfMonth(viewDate), weekStartsOn), [viewDate, weekStartsOn]);
  const days: Date[] = useMemo(() => Array.from({ length: 42 }, (_, i) => addDays(gridStart, i)), [gridStart]);

  const weekdayLabels =
    weekStartsOn === 1
      ? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
      : ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  function prevMonth() { setViewDate(addMonths(viewDate, -1)); }
  function nextMonth() { setViewDate(addMonths(viewDate, 1)); }
  function goToday() { const t = startOfMonth(today); setViewDate(t); setSelectedDate(today); }

  const selectedKey = ymd(selectedDate);
  const selectedEvents = eventsByDay.get(selectedKey) ?? [];

  const authHelp = error && /not authenticated/i.test(error)
    ? "Connect your Google account from Settings to view your calendar."
    : null;

  return (
    <div className="min-h-screen bg-background text-foreground p-4 md:p-6">
      <div className="mx-auto max-w-6xl grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Header / Controls span full width on small screens */}
        <div className="lg:col-span-3">
          <Card className="bg-card border border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle className="flex items-center gap-2 text-xl">
                <CalendarIcon className="h-5 w-5" />
                {formatMonthYear(viewDate)}
                {isLoading && (
                  <span className="text-xs font-normal text-muted-foreground">Syncing...</span>
                )}
              </CardTitle>
              <div className="flex items-center gap-2">
                <Button variant="outline" onClick={goToday}>Today</Button>
                <Button variant="outline" size="icon" onClick={prevMonth} aria-label="Previous month">
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={nextMonth} aria-label="Next month">
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            {(error || authHelp) && (
              <div className="px-6 pb-4 text-sm text-destructive">
                {authHelp ?? `Error loading events: ${error}`}
              </div>
            )}
          </Card>
        </div>

        {/* Month grid */}
        <div className="lg:col-span-2">
          <Card className="bg-card border border-border">
            <CardHeader className="pb-2">
              <div className="grid grid-cols-7 text-sm text-muted-foreground">
                {weekdayLabels.map((d) => (
                  <div key={d} className="px-2 py-1">{d}</div>
                ))}
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div role="grid" className="grid grid-cols-7 gap-1 sm:gap-2">
                {days.map((day) => {
                  const inMonth = isSameMonth(day, viewDate);
                  const isToday = isSameDay(day, today);
                  const isSelected = isSameDay(day, selectedDate);
                  const key = ymd(day);
                  const dayEvents = eventsByDay.get(key) ?? [];

                  return (
                    <button
                      key={key}
                      role="gridcell"
                      onClick={() => setSelectedDate(day)}
                      className={[
                        "group flex flex-col rounded-lg border p-2 text-left transition-colors",
                        "bg-background hover:bg-accent",
                        "border-border",
                        !inMonth && "text-muted-foreground/60",
                        isSelected && "ring-2 ring-primary",
                      ].filter(Boolean).join(" ")}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">
                          {day.getDate()}
                        </span>
                        {isToday && (
                          <span className="text-[10px] rounded px-1 py-0.5 bg-primary text-primary-foreground">
                            Today
                          </span>
                        )}
                      </div>

                      {/* event chips (up to 3) */}
                      <div className="mt-2 space-y-1">
                        {dayEvents.slice(0, 3).map((ev) => (
                          <div
                            key={ev.id}
                            className="truncate rounded-md bg-muted px-2 py-1 text-xs text-foreground border border-border/60"
                            title={ev.title}
                          >
                            {ev.title}
                          </div>
                        ))}
                        {dayEvents.length > 3 && (
                          <div className="text-[11px] text-muted-foreground">
                            +{dayEvents.length - 3} more
                          </div>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Selected day events */}
        <div className="lg:col-span-1">
          <Card className="bg-card border border-border h-full">
            <CardHeader>
              <CardTitle className="text-base">
                {selectedDate.toLocaleDateString(undefined, {
                  weekday: "long", month: "short", day: "numeric",
                })}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <p className="text-sm text-muted-foreground">Loading events...</p>
              ) : selectedEvents.length === 0 ? (
                <p className="text-sm text-muted-foreground">No events.</p>
              ) : (
                <ul className="space-y-2">
                  {selectedEvents.map((ev) => (
                    <li key={ev.id} className="rounded-lg border border-border bg-muted p-3">
                      <div className="text-sm font-medium text-foreground">{ev.title}</div>
                      {ev.where && (
                        <div className="text-xs text-muted-foreground mt-0.5">{ev.where}</div>
                      )}
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {formatTimeRange(ev)}
                      </div>
                      {ev.description && (
                        <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                          {ev.description}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ---------- helpers for event times ---------- */
function formatTimeRange(ev: CalEvent) {
  const s = toDate(ev.start);
  const e = ev.end ? toDate(ev.end) : null;
  const fmt = (d: Date) => d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return e ? `${fmt(s)} - ${fmt(e)}` : fmt(s);
}



