#!/usr/bin/env python3
"""Validate performance metrics against configurable thresholds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to a JSON metrics file.")
    parser.add_argument("--metric", required=True, help="Metric name within the JSON payload.")
    parser.add_argument("--max", type=float, help="Maximum allowed value for the metric.")
    parser.add_argument("--min", type=float, help="Minimum allowed value for the metric.")
    args = parser.parse_args()

    data = json.loads(args.report.read_text(encoding="utf-8"))
    metric_value = data
    for part in args.metric.split(":"):
        if isinstance(metric_value, dict) and part in metric_value:
            metric_value = metric_value[part]
        else:
            raise SystemExit(f"Metric '{args.metric}' not found in report {args.report}")
    if not isinstance(metric_value, (int, float)):
        raise SystemExit(f"Metric '{args.metric}' is not numeric (value={metric_value!r}).")

    if args.max is not None and metric_value > args.max:
        raise SystemExit(f"Metric '{args.metric}' exceeded threshold: {metric_value} > {args.max}")
    if args.min is not None and metric_value < args.min:
        raise SystemExit(f"Metric '{args.metric}' below threshold: {metric_value} < {args.min}")


if __name__ == "__main__":
    main()
