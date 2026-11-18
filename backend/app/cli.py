"""Command-line admin tasks.

    python -m app.cli make-admin someone@example.com
    python -m app.cli remove-admin someone@example.com

There is deliberately no way to become an admin through the API or the
website: the first admin must be promoted here, by someone with server access.
"""

import asyncio
import sys
from datetime import UTC, datetime

from app.core.config import get_settings
from app.db import mongo
from app.db.mongo import AUDIT_LOG, USERS


async def _set_role(email: str, role: str) -> int:
    db = await mongo.connect(get_settings())
    try:
        result = await db[USERS].update_one({"email": email.strip().lower()}, {"$set": {"role": role}})
        if result.matched_count == 0:
            print(f"No user found with email {email}. They must register first.")
            return 1
        await db[AUDIT_LOG].insert_one(
            {"admin_id": "cli", "action": f"user.role_changed_via_cli", "target_id": None,
             "details": {"to": role}, "created_at": datetime.now(UTC)}
        )
        print(f"{email} is now: {role}")
        return 0
    finally:
        await mongo.close()


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"make-admin", "remove-admin"}:
        print(__doc__)
        return 2
    role = "admin" if sys.argv[1] == "make-admin" else "user"
    return asyncio.run(_set_role(sys.argv[2], role))


if __name__ == "__main__":
    raise SystemExit(main())
