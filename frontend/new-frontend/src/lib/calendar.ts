export type CalendarEventApi = {
  id: string | null;
  title: string;
  start_time: string;
  end_time?: string | null;
  description?: string | null;
  location?: string | null;
  attendees: string[];
};

export type CalendarEventsResponse = {
  success: boolean;
  count: number;
  start: string;
  end: string;
  events: CalendarEventApi[];
};

export type CalendarEventsRequest = {
  start: Date;
  end: Date;
  signal?: AbortSignal;
};

function buildQuery(params: { start: Date; end: Date }): string {
  const search = new URLSearchParams({
    start: params.start.toISOString(),
    end: params.end.toISOString(),
  });
  return search.toString();
}

export async function fetchCalendarEvents({ start, end, signal }: CalendarEventsRequest): Promise<CalendarEventsResponse> {
  const query = buildQuery({ start, end });
  const response = await fetch(`/api/calendar/events?${query}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    signal,
  });

  const rawText = await response.text();
  let parsed: unknown = undefined;

  if (rawText) {
    try {
      parsed = JSON.parse(rawText);
    } catch {
      parsed = undefined;
    }
  }

  if (!response.ok) {
    const message =
      parsed && typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? String((parsed as Record<string, unknown>).detail)
        : `Calendar request failed with status ${response.status}`;
    throw new Error(message);
  }

  if (!parsed || typeof parsed !== "object") {
    throw new Error("Calendar service returned an unexpected response.");
  }

  const data = parsed as CalendarEventsResponse;
  if (!Array.isArray(data.events)) {
    throw new Error("Calendar response did not include event data.");
  }

  return data;
}
