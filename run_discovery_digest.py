#!/usr/bin/env python3
"""
run_discovery_digest.py — standalone weekly runner for the Discovery Digest.

Invoked by a weekly cron (Monday, after the daily discovery cron has written
discovery_log.json). Kept OUT of sentinel.py's main loop on purpose: this is an
isolated, brain-safe entrypoint that cannot affect the live sentinel daemon.

Cron (installed separately):
  30 6 * * 1  cd /opt/sentinel && venv/bin/python run_discovery_digest.py >> discovery_digest.log 2>&1
  # 06:30 UTC Monday = ~09:30 Israel, just after the 06:00 UTC discovery cron.

Manual test:
  cd /opt/sentinel && venv/bin/python run_discovery_digest.py --no-empty
"""

import logging
import sys
from pathlib import Path

SENTINEL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SENTINEL_DIR))


def _alert(reason: str) -> None:
    """Failure-alert guard: ping Telegram if the weekly digest did not run/send.
    Best-effort — if Telegram itself is the failure, this can't deliver either,
    but the common cases (Claude error, code error, discovery_log missing) do reach it.
    """
    try:
        import notifier
        notifier._api(
            "sendMessage",
            chat_id=notifier._chat(),
            text=f"⚠️ <b>Discovery Digest failed</b>\n{reason}\n"
                 "<i>Weekly run did not complete — check discovery_digest.log on the VPS.</i>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logging.error("failure-alert could not be sent: %s", e)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
    )
    # Load the same env the sentinel daemon uses (ANTHROPIC_API_KEY, TELEGRAM_*).
    try:
        from dotenv import load_dotenv
        load_dotenv(SENTINEL_DIR / ".env")
    except Exception as e:  # dotenv missing or .env absent — env may already be exported
        logging.warning("dotenv load skipped: %s", e)

    send_empty = "--no-empty" not in sys.argv
    try:
        import discovery_digest
        result = discovery_digest.run_digest(send_empty=send_empty)
        logging.info("discovery digest result: %s", result)
        # Candidates existed but nothing was sent → a real failure worth alerting on.
        if result.get("count", 0) > 0 and not result.get("sent"):
            _alert(f"Analyzed {result.get('count')} candidate(s) but the Telegram send failed.")
            return 1
        return 0
    except Exception as e:
        logging.exception("discovery digest crashed")
        _alert(f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
