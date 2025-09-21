import { auth } from "./firebase";

const DEFAULT_BASE_URL = "http://localhost:8000";
const baseUrl =
  (import.meta.env.VITE_BACKEND_URL as string | undefined)?.replace(/\/?$/, "") ||
  DEFAULT_BASE_URL;

/** Backend request/response types */
export type ChatRequestPayload = {
  message: string;
  user_id: string; // irrelevant to your logic; send empty
  conversation_id: string; // irrelevant to your logic; send empty
  context: Record<string, unknown>; // irrelevant; send {}
};

export type ChatResponsePayload = {
  message: string; // backend's reply text
  success: boolean;
  conversation_id: string;
  data?: Record<string, unknown>;
  suggestions?: string[];
  requires_confirmation?: boolean;
  agent_actions?: string[];
  timestamp?: string;
};

export async function requestChatReply(
  message: string,
  signal?: AbortSignal
): Promise<string> {
  const headers = new Headers({ "Content-Type": "application/json" });

  // Attach Firebase auth if available
  const current = auth.currentUser;
  if (current) {
    const token = await current.getIdToken();
    headers.set("Authorization", `Bearer ${token}`);
  }

  const payload: ChatRequestPayload = {
    message,
    user_id: "", // not used by your app
    conversation_id: "", // not used by your app
    context: {}, // not used by your app
  };

  const response = await fetch(`${baseUrl}/api/chat/message`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
    // mode: "cors" is default in browsers for cross-origin; leaving explicit is fine too:
    // mode: "cors",
  });

  // Try to surface any server-provided error text/json
  if (!response.ok) {
    let errText = "";
    try {
      // Attempt JSON first
      const maybeJson = await response.json();
      errText =
        typeof maybeJson?.message === "string"
          ? maybeJson.message
          : JSON.stringify(maybeJson);
    } catch {
      try {
        errText = await response.text();
      } catch {
        // ignore
      }
    }
    throw new Error(errText || `Chat request failed with status ${response.status}`);
  }

  const data = (await response.json()) as Partial<ChatResponsePayload>;

  if (typeof data.message !== "string") {
    throw new Error("Chat response was malformed: missing 'message' string.");
  }

  return data.message;
}
