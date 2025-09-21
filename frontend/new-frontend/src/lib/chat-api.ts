import { auth } from "./firebase";

const DEFAULT_BASE_URL = "http://localhost:8000";
const baseUrl = (import.meta.env.VITE_BACKEND_URL as string | undefined)?.replace(/\/?$/, "") || DEFAULT_BASE_URL;

export type ChatRequestPayload = {
  message: string;
};

export type ChatResponsePayload = {
  reply: string;
};

export async function requestChatReply(message: string, signal?: AbortSignal): Promise<string> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const current = auth.currentUser;

  if (current) {
    const token = await current.getIdToken();
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${baseUrl}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message } satisfies ChatRequestPayload),
    signal,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `Chat request failed with status ${response.status}`);
  }

  const data = (await response.json()) as Partial<ChatResponsePayload>;
  if (typeof data.reply !== "string") {
    throw new Error("Chat response was malformed.");
  }

  return data.reply;
}
