import { auth } from "./firebase";

const DEFAULT_BASE_URL = "http://localhost:8000";
const envBaseUrl = (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "";
const baseUrl = (envBaseUrl || DEFAULT_BASE_URL).replace(/\/+$/, "");

export type ChatRequestPayload = {
  message: string;
  user_id: string;
  conversation_id?: string;
  context?: Record<string, unknown>;
};

export type ChatResponsePayload = {
  message: string;
  success: boolean;
  conversation_id: string;
  data?: Record<string, unknown> | null;
  suggestions?: string[] | null;
  requires_confirmation: boolean;
  agent_actions?: string[] | null;
  timestamp?: string;
};

export type RequestChatReplyOptions = {
  message: string;
  userId: string;
  conversationId?: string;
  context?: Record<string, unknown>;
  signal?: AbortSignal;
};

export async function requestChatReply({
  message,
  userId,
  conversationId,
  context,
  signal,
}: RequestChatReplyOptions): Promise<ChatResponsePayload> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const current = auth.currentUser;

  if (current) {
    const token = await current.getIdToken();
    headers.set("Authorization", `Bearer ${token}`);
  }

  const payload: ChatRequestPayload = {
    message,
    user_id: userId,
  };

  if (conversationId) {
    payload.conversation_id = conversationId;
  }

  if (context && Object.keys(context).length > 0) {
    payload.context = context;
  }

  const response = await fetch(`${baseUrl}/api/chat/message`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    let details = `Chat request failed with status ${response.status}`;

    try {
      const errorBody = await response.json();
      if (typeof errorBody?.error === "string") {
        details = errorBody.error;
      } else if (typeof errorBody?.message === "string") {
        details = errorBody.message;
      }
    } catch {
      const text = await response.text().catch(() => "");
      if (text) {
        details = text;
      }
    }

    throw new Error(details);
  }

  const data = (await response.json()) as Partial<ChatResponsePayload>;

  if (typeof data.message !== "string" || typeof data.conversation_id !== "string") {
    throw new Error("Chat response was malformed.");
  }

  return {
    message: data.message,
    success: Boolean(data.success),
    conversation_id: data.conversation_id,
    data: data.data ?? null,
    suggestions: data.suggestions ?? null,
    requires_confirmation: Boolean(data.requires_confirmation),
    agent_actions: data.agent_actions ?? null,
    timestamp: typeof data.timestamp === "string" ? data.timestamp : undefined,
  };
}
