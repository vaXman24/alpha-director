# Calibration integrity fixes

These three runtime modules were adopted from the deployed service and corrected together. The generator shares the scorer's quote validation, so deploy both from the same revision.

## Behavior

- Reject non-finite, non-positive, future-dated, and older-than-four-days quotes. Do not substitute signal-change history for a current quote.
- Defer scoring when entry/exit data is unavailable instead of manufacturing a MISS.
- Classify a trailing-stop exit at or below entry as STOP instead of WIN; preserve the observed exit price.
- Retain an explicit zero forecast probability and the divergence snapshot recorded at entry.
- Skip calibration events older than downloaded price coverage rather than moving their entries to the first available bar.

## Validation

From the repository root, run `python tests/test_calibration_integrity.py`. The 19 tests mock external data and persistence; they do not write to a live database, send notifications, or execute trades.

## Deployment

Copy `thesis_scorer.py`, `thesis_generator.py`, and `source_calibrator.py` from this directory into the service directory as one release. Verify the running source has not changed since review, back up all three originals, run the tests with the service Python, stop the service while replacing the group, preserve owner/mode, and restart with health verification. Roll back the entire group on failure.

## Limits

The four-calendar-day quote limit is not an exchange calendar, and daily prices do not reproduce intraday execution. This change does not rescore historical outcomes, redefine the research target, modify Kelly allocation, or promote shadow strategies to capital. A delayed expiry still needs an explicit historical-price execution model for a complete research protocol.
