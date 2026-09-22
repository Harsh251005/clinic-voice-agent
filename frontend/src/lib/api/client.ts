// The dashboard API, typed from FastAPI's schema (npm run api:types).
// Same origin: Next forwards /api/* to FastAPI, so the session cookie just works.
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

export const api = createClient<paths>({
  baseUrl: "",
  credentials: "same-origin",
  // Required on every change (CSRF): a form on another site can't add it.
  headers: { "x-clinic-console": "1" },
});

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

/** The data, or an ApiError carrying the API's own message (e.g. a 422's
 *  "The link name is already taken"), ready to show to staff. */
export async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await request;
  if (response.ok) return data as T;
  throw new ApiError(response.status, messageOf(error, response.status));
}

function messageOf(error: unknown, status: number): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg); // FastAPI validation
  if (status >= 500) return "Something went wrong on the server. Try again.";
  return "That didn't work. Try again.";
}
