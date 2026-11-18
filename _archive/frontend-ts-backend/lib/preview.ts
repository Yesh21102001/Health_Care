/**
 * UI PREVIEW MODE
 *
 * While true:
 * - the signed-in screens (dashboard, chat, history, report, profile) show
 *   SAMPLE data from lib/mock/data.ts and make no API calls;
 * - proxy.ts does not require a login, so you can browse them freely;
 * - every signed-in screen shows a "Preview" banner.
 *
 * Set to false when the frontend is connected to the backend.
 */
export const UI_PREVIEW = true;
