import { auth } from "./firebase";

export async function authedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
  { forceRefresh }: { forceRefresh?: boolean } = {}
) {
  const current = auth.currentUser;
  if (!current) {
    throw new Error("You need to be signed in before making authenticated requests.");
  }

  const token = await current.getIdToken(forceRefresh);
  const headers = new Headers(init.headers ?? {});
  headers.set("Authorization", `Bearer ${token}`);

  return fetch(input, {
    ...init,
    headers,
  });
}
