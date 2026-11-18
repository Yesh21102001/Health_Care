"""Email delivery: NOT connected yet.

- Development: the reset link is printed to the terminal running the API,
  so you can test the full flow locally.
- Production: nothing is sent and an error is logged. Connect a provider
  (Resend, Amazon SES, Postmark, ...) here before launch.
"""

from app.core.config import Settings
from app.core.logging import log_error


async def send_password_reset_email(settings: Settings, to: str, name: str, reset_url: str) -> None:
    if not settings.is_production:
        print(f"\n[dev mail] Password reset requested for {to} ({name}).\n[dev mail] Open this link: {reset_url}\n", flush=True)
        return
    log_error("mail.not_configured", kind="password_reset")
