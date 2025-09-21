export type ChatApiResponse = {
  message?: string;
  success: boolean;
  conversation_id?: string;
  data?: Record<string, unknown>;
  suggestions?: string[];
  requires_confirmation?: boolean;
  agent_actions?: string[];
  timestamp?: string;
};

export type ChatApiRequest = {
  message: string;
  userId: string;
  conversationId?: string;
};

export async function sendChatMessage(payload: ChatApiRequest): Promise<ChatApiResponse> {
  const body = {
    message: payload.message,
    user_id: payload.userId,
    ...(payload.conversationId ? { conversation_id: payload.conversationId } : {}),
  };

  const response = await fetch("/api/chat/message", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
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
      parsed && typeof parsed === "object" && "message" in (parsed as Record<string, unknown>)
        ? String((parsed as Record<string, unknown>).message)
        : `Chat request failed with status ${response.status}`;
    throw new Error(message);
  }

  if (!parsed || typeof parsed !== "object") {
    throw new Error("Chat service returned an unexpected response.");
  }

  return parsed as ChatApiResponse;
}

export function formatChatReply(response: ChatApiResponse): string {
  const pieces: string[] = [];
  const mainMessage = typeof response.message === "string" && response.message.trim().length > 0
    ? response.message
    : "The agent did not return any message.";
  pieces.push(mainMessage);

  if (response.requires_confirmation) {
    pieces.push("The agent needs your confirmation to finish this request.");
  }

  if (response.suggestions?.length) {
    pieces.push(`Suggestions: ${response.suggestions.join(", ")}`);
  }

  if (response.agent_actions?.length) {
    pieces.push(`Agent actions: ${response.agent_actions.join(", ")}`);
  }

  if (!response.success) {
    pieces.push("The agent reported a problem while processing your request.");
  }

  return pieces.filter(Boolean).join("\n\n");
}
