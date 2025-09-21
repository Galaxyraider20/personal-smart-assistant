import React, { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon } from "lucide-react";

/** Basic event type */
export type CalEvent = {
  id: string;
  title: string;
  start: Date | string; // accepts ISO string or Date
  end?: Date | string;
  where?: string;
};

interface CalendarProps {
  events?: CalEvent[];
  weekStartsOn?: 0 | 1; // 0=Sun, 1=Mon
}

const sampleEvents: CalEvent[] = [
  { id: "1", title: "Team standup", start: new Date(), where: "Meet" },
  { id: "2", title: "Design review", start: addDays(new Date(), 1) },
  { id: "3", title: "1:1 Catch-up", start: addDays(new Date(), 2), where: "Room A" },
  { id: "4", title: "Demo prep", start: addDays(new Date(), 2) },
  { id: "5", title: "Sprint planning", start: addDays(new Date(), 7) },
];

/* ---------- tiny date helpers (no deps) ---------- */
function startOfDay(d: Date) { const x = new Date(d); x.setHours(0,0,0,0); return x; }
function isSameDay(a: Date, b: Date) { return startOfDay(a).getTime() === startOfDay(b).getTime(); }
function isSameMonth(a: Date, b: Date) { return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth(); }
function addDays(d: Date, n: number) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function addMonths(d: Date, n: number) { const x = new Date(d); x.setMonth(x.getMonth() + n); return x; }
function startOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function endOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth()+1, 0); }
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

/* ---------- the component ---------- */
export default function CalendarPage({
  events = sampleEvents,
  weekStartsOn = 0,
}: CalendarProps) {
  const today = startOfDay(new Date());
  const [viewDate, setViewDate] = useState<Date>(startOfMonth(today));
  const [selectedDate, setSelectedDate] = useState<Date>(today);

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
  const gridStart = startOfWeek(startOfMonth(viewDate), weekStartsOn);
  const days: Date[] = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));

  const weekdayLabels =
    weekStartsOn === 1
      ? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
      : ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  function prevMonth() { setViewDate(addMonths(viewDate, -1)); }
  function nextMonth() { setViewDate(addMonths(viewDate, 1)); }
  function goToday() { const t = startOfMonth(today); setViewDate(t); setSelectedDate(today); }

  const selectedKey = ymd(selectedDate);
  const selectedEvents = eventsByDay.get(selectedKey) ?? [];

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
              {selectedEvents.length === 0 ? (
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
  return e ? `${fmt(s)} – ${fmt(e)}` : fmt(s);
}
