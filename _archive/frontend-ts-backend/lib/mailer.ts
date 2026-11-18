import "server-only";
import { isProduction } from "@/lib/env";
import { logger } from "@/lib/logger";

/*
 * Email delivery is NOT connected yet.
 *
 * - Development: the reset link is printed to the terminal running `npm run dev`
 *   so you can test the full flow locally.
 * - Production: nothing is sent and an error is logged. Connect a provider
 *   (e.g. Resend, Amazon SES, Postmark) here before launch.
 */
export async function sendPasswordResetEmail(to: string, name: string, resetUrl: string): Promise<void> {
  if (!isProduction) {
    console.info(
      `\n[dev mail] Password reset requested for ${to} (${name}).\n[dev mail] Open this link to reset: ${resetUrl}\n`,
    );
    return;
  }
  logger.error("mail.not_configured", new Error("No email provider configured"), { kind: "password_reset" });
}
