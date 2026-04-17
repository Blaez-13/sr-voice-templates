#!/usr/bin/env python3
"""
monitor.py — Pull post-call analysis from ElevenLabs, check against alert thresholds, and page on breach.

PURPOSE
-------
monitor.py is the nightly production monitoring script for deployed SR Voice agents.
It is invoked by Cloud Scheduler (Carl wires the schedule separately).

For each active client agent, it:

  1. Pulls the last 24 hours of call analysis data from ElevenLabs via REST API
     (or from Firestore if post-call webhook capture is confirmed complete)
  2. Computes rolling 7-day metrics per client:
       - triage_accuracy: % of calls where triage_correct=true
       - emergency_misroute_count: calls where emergency_keywords_present=true AND escalated_to_human=false
       - tool_success_rate: tool_calls_succeeded / tool_calls_attempted
       - booking_completion_rate: % of booking-intent calls that result in confirmed appointment
       - negative_sentiment_rate: % of calls ending with negative caller_sentiment
  3. Compares metrics against the alert threshold matrix (config/alert-thresholds.js)
  4. Sends alerts via Better Stack if any threshold is breached
  5. Writes a summary JSON to Firestore for the admin dashboard

ALERT THRESHOLDS (from decision D6)
-------------------------------------
  triage_accuracy:       warn <92%, page <85%
  emergency_misroute:    warn >=1 event, page >=2 events (rolling 7 days)
  tool_success_rate:     warn <95%, page <90%
  booking_completion:    warn <70%, page <50%
  negative_sentiment:    warn >15%, page >25%

USAGE
-----
  python deploy/monitor.py \\
    [--client-slug my-client]   # Monitor a single client; default: all active clients
    [--lookback-days 7]         # Rolling window in days (default: 7)
    [--dry-run]                 # Compute metrics but do not send alerts

ENVIRONMENT VARIABLES
---------------------
  ELEVENLABS_API_KEY       — Required. ElevenLabs API key.
  BETTERSTACK_SOURCE_TOKEN — Required for alerting. Better Stack log source token.
  GOOGLE_APPLICATION_CREDENTIALS — Required. Path to Firebase service account key.

IMPLEMENTATION STATUS
---------------------
This is a STUB. The docstring, argument structure, and function contracts are complete.
Full implementation is wired in Task H (Phase 3) and depends on Task D (post-call analysis
webhook capture) being complete.

The following functions are defined as stubs with their contracts:
  - fetch_analysis_data(client_slug, lookback_days) -> list[dict]
  - compute_metrics(analysis_records) -> dict
  - check_thresholds(metrics, thresholds) -> list[dict]  (returns list of breaches)
  - send_alert(breach, client_slug) -> bool
  - write_firestore_summary(client_slug, metrics, breaches) -> None

EXIT CODES
----------
  0 — All clients checked, no threshold breaches
  1 — One or more threshold breaches detected (alerts sent if not dry-run)
  2 — API error: could not reach ElevenLabs or Firestore
"""

import argparse
import sys


ALERT_THRESHOLDS = {
    "triage_accuracy":         {"warn": 0.92, "page": 0.85},
    "emergency_misroute":      {"warn": 1,    "page": 2},       # event counts, not rates
    "tool_success_rate":       {"warn": 0.95, "page": 0.90},
    "booking_completion_rate": {"warn": 0.70, "page": 0.50},
    "negative_sentiment_rate": {"warn": 0.15, "page": 0.25},
}


def fetch_analysis_data(client_slug: str, lookback_days: int = 7) -> list:
    """
    Pull post-call analysis records for a client from ElevenLabs REST API
    and cross-reference against Firestore call_analysis subcollection.

    Args:
        client_slug: The client's slug identifier.
        lookback_days: Number of days of history to fetch.

    Returns:
        List of analysis record dicts, one per call, containing all fields
        written by the ElevenLabs post-call webhook handler.
    """
    # STUB — Task H implements via GET /v1/convai/conversations + Firestore read
    raise NotImplementedError("monitor.py: fetch_analysis_data() not yet implemented — wired in Task H")


def compute_metrics(analysis_records: list) -> dict:
    """
    Compute rolling aggregate metrics from a list of analysis records.

    Args:
        analysis_records: List of analysis dicts from fetch_analysis_data().

    Returns:
        Metrics dict with keys matching ALERT_THRESHOLDS, plus:
          call_count (int), period_start (str), period_end (str)
    """
    # STUB — Task H implements aggregation logic
    raise NotImplementedError("monitor.py: compute_metrics() not yet implemented — wired in Task H")


def check_thresholds(metrics: dict, thresholds: dict) -> list:
    """
    Compare computed metrics against threshold matrix and return a list of breaches.

    Args:
        metrics: Computed metrics dict from compute_metrics().
        thresholds: Threshold matrix dict (ALERT_THRESHOLDS by default).

    Returns:
        List of breach dicts, each containing:
          metric (str), value (float), threshold_level ('warn'|'page'), threshold_value (float)
    """
    # STUB — Task H implements threshold comparison
    raise NotImplementedError("monitor.py: check_thresholds() not yet implemented — wired in Task H")


def send_alert(breach: dict, client_slug: str, dry_run: bool = False) -> bool:
    """
    Send an alert to Better Stack for a threshold breach.

    Args:
        breach: Breach dict from check_thresholds().
        client_slug: Client identifier for the alert message.
        dry_run: If True, log the alert but do not send.

    Returns:
        True if alert was sent (or dry_run), False if send failed.
    """
    # STUB — Task H implements via Better Stack Logs API (POST to source URL)
    raise NotImplementedError("monitor.py: send_alert() not yet implemented — wired in Task H")


def write_firestore_summary(client_slug: str, metrics: dict, breaches: list) -> None:
    """
    Write the monitoring summary to Firestore for the admin dashboard.

    Document path: clients/{slug}/monitoring/latest

    Args:
        client_slug: Client identifier.
        metrics: Computed metrics dict.
        breaches: List of breach dicts (empty list if no breaches).
    """
    # STUB — Task H implements via Firebase Admin SDK Firestore write
    raise NotImplementedError("monitor.py: write_firestore_summary() not yet implemented — wired in Task H")


def main():
    parser = argparse.ArgumentParser(
        description="Pull post-call analysis, check thresholds, alert on breach."
    )
    parser.add_argument("--client-slug", help="Monitor a single client by slug (default: all active clients)")
    parser.add_argument("--lookback-days", type=int, default=7, help="Rolling window in days (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Compute metrics but do not send alerts")
    args = parser.parse_args()

    print(f"[monitor.py] STUB — implementation pending Task H")
    print(f"  client-slug:   {args.client_slug or 'all'}")
    print(f"  lookback-days: {args.lookback_days}")
    print(f"  dry-run:       {args.dry_run}")
    print(f"  thresholds:    {ALERT_THRESHOLDS}")
    sys.exit(0)


if __name__ == "__main__":
    main()
