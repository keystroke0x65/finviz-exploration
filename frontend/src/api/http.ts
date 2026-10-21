const NO_CONTENT = 204;

interface ValidationIssue {
  msg: string;
}

function describeErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }
  // FastAPI request validation errors (422) send a list of issues.
  if (Array.isArray(detail)) {
    const messages = detail
      .filter((issue): issue is ValidationIssue => typeof issue?.msg === "string")
      .map((issue) => issue.msg);
    return messages.length > 0 ? messages.join("; ") : null;
  }
  return null;
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = init ? await fetch(path, init) : await fetch(path);

  if (!response.ok) {
    // The backend normally sends { detail } (FastAPI's HTTPException shape),
    // but an unhandled 500 can return an HTML error page instead, so the body
    // isn't guaranteed to be valid JSON.
    const body = await response.json().catch(() => null);
    throw new Error(describeErrorDetail(body?.detail) ?? `Request failed (${response.status})`);
  }

  if (response.status === NO_CONTENT) {
    return undefined as T;
  }
  // The backend's response models define these shapes; the types here mirror
  // backend/app/schemas.py rather than re-validating our own API.
  return (await response.json()) as T;
}

export function jsonRequest(method: "POST" | "PUT" | "PATCH", body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
