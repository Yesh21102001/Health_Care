import "server-only";

/*
 * Minimal structured logger. Rule: log events and IDs, never request bodies,
 * passwords, tokens, emails or health content.
 */
type Fields = Record<string, string | number | boolean | null | undefined>;

function write(level: "info" | "warn" | "error", event: string, fields: Fields = {}) {
  const line = JSON.stringify({ level, event, time: new Date().toISOString(), ...fields });
  if (level === "error") console.error(line);
  else if (level === "warn") console.warn(line);
  else console.info(line);
}

export const logger = {
  info: (event: string, fields?: Fields) => write("info", event, fields),
  warn: (event: string, fields?: Fields) => write("warn", event, fields),
  // Only the error's name and code are logged: messages from drivers can embed
  // user data (e.g. MongoDB duplicate-key errors include the duplicate email).
  error: (event: string, err: unknown, fields?: Fields) =>
    write("error", event, {
      ...fields,
      errorName: err instanceof Error ? err.name : "unknown",
      errorCode:
        typeof err === "object" && err !== null && "code" in err ? String((err as { code: unknown }).code) : undefined,
    }),
};
