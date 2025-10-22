#!/usr/bin/env python3
"""Profile OmniSpatial workflows and record resource utilisation."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import psutil

try:  # Optional GPU sampling
    import pynvml  # type: ignore

    pynvml.nvmlInit()
    _GPU_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency / no GPU
    _GPU_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "omnispatial" / "src"
for candidate in (str(SRC_ROOT), str(PROJECT_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

@dataclass
class Sample:
    timestamp: float
    rss_bytes: int
    process_cpu: float
    system_cpu: float
    read_bytes: Optional[int]
    write_bytes: Optional[int]
    gpu_util: Optional[float]
    gpu_mem: Optional[float]


class Sampler(threading.Thread):
    def __init__(self, interval: float = 0.5) -> None:
        super().__init__(daemon=True)
        self.interval = interval
        self.process = psutil.Process(os.getpid())
        self.samples: List[Sample] = []
        self._stop = threading.Event()
        self._io_available = hasattr(self.process, "io_counters")

        # Prime CPU measurement
        self.process.cpu_percent(None)
        psutil.cpu_percent(None)

    def run(self) -> None:  # pragma: no cover - thread timing dependent
        while not self._stop.is_set():
            time.sleep(self.interval)
            timestamp = time.time()
            rss = self.process.memory_info().rss
            cpu = self.process.cpu_percent(None)
            system_cpu = psutil.cpu_percent(None)
            io_counters = self.process.io_counters() if self._io_available else None
            read_bytes = io_counters.read_bytes if io_counters else None
            write_bytes = io_counters.write_bytes if io_counters else None
            gpu_util = None
            gpu_mem = None
            if _GPU_AVAILABLE:
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_util = float(util.gpu)
                    gpu_mem = float(mem.used) / (1024**3)
                except Exception:  # pragma: no cover - runtime GPU failure
                    gpu_util = None
                    gpu_mem = None
            self.samples.append(
                Sample(
                    timestamp=timestamp,
                    rss_bytes=rss,
                    process_cpu=cpu,
                    system_cpu=system_cpu,
                    read_bytes=read_bytes,
                    write_bytes=write_bytes,
                    gpu_util=gpu_util,
                    gpu_mem=gpu_mem,
                )
            )

    def stop(self) -> None:
        self._stop.set()


class ProfileSession:
    def __init__(self, label: str, interval: float = 0.5) -> None:
        self.label = label
        self.interval = interval
        self.sampler = Sampler(interval=interval)
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.summary: Dict[str, float | str | None] = {}

    def __enter__(self) -> "ProfileSession":
        self.start_time = time.time()
        self.sampler.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.sampler.stop()
        self.sampler.join()
        self.end_time = time.time()
        self.summary = self._compute_summary()

    def _compute_summary(self) -> Dict[str, float | str | None]:
        duration = (self.end_time or time.time()) - (self.start_time or time.time())
        if not self.sampler.samples:
            return {"label": self.label, "duration_s": duration}

        rss_peak = max(sample.rss_bytes for sample in self.sampler.samples) / (1024**3)
        cpu_avg = sum(sample.process_cpu for sample in self.sampler.samples) / len(self.sampler.samples)
        cpu_peak = max(sample.process_cpu for sample in self.sampler.samples)
        system_cpu_avg = sum(sample.system_cpu for sample in self.sampler.samples) / len(self.sampler.samples)
        read_total = None
        write_total = None
        first = self.sampler.samples[0]
        last = self.sampler.samples[-1]
        if first.read_bytes is not None and last.read_bytes is not None:
            read_total = (last.read_bytes - first.read_bytes) / (1024**2)
        if first.write_bytes is not None and last.write_bytes is not None:
            write_total = (last.write_bytes - first.write_bytes) / (1024**2)
        gpu_util_peak = None
        gpu_mem_peak = None
        gpu_samples = [sample.gpu_util for sample in self.sampler.samples if sample.gpu_util is not None]
        gpu_mem_samples = [sample.gpu_mem for sample in self.sampler.samples if sample.gpu_mem is not None]
        if gpu_samples:
            gpu_util_peak = max(gpu_samples)
        if gpu_mem_samples:
            gpu_mem_peak = max(gpu_mem_samples)

        return {
            "label": self.label,
            "duration_s": duration,
            "process_cpu_avg": cpu_avg,
            "process_cpu_peak": cpu_peak,
            "system_cpu_avg": system_cpu_avg,
            "rss_peak_gb": rss_peak,
            "read_mb": read_total,
            "write_mb": write_total,
            "gpu_util_peak": gpu_util_peak,
            "gpu_mem_peak_gb": gpu_mem_peak,
            "sample_count": len(self.sampler.samples),
        }

    def emit(self, report_path: Path, metadata: Dict[str, object]) -> None:
        payload = {
            "summary": self.summary,
            "metadata": metadata,
            "samples": [sample.__dict__ for sample in self.sampler.samples],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def parse_chunks(chunk_str: Optional[str], dims: int) -> Optional[tuple[int, ...]]:
    if chunk_str is None:
        return None
    parts = [int(part.strip()) for part in chunk_str.split(",") if part.strip()]
    if len(parts) != dims:
        raise ValueError(f"Expected {dims} comma-separated integers, received {chunk_str}")
    return tuple(parts)


def run_convert(args: argparse.Namespace) -> Dict[str, object]:
    from omnispatial import api

    result = api.convert(
        input_path=args.input,
        out=args.out,
        vendor=args.vendor,
        output_format=args.format,
        dry_run=args.dry_run,
        image_chunks=parse_chunks(args.image_chunks, 3),
        label_chunks=parse_chunks(args.label_chunks, 2),
        compressor=args.compressor,
        compression_level=args.compression_level,
    )
    return {
        "task": "convert",
        "adapter": result.adapter,
        "output": str(result.output_path) if result.output_path else None,
        "format": result.format,
        "dry_run": args.dry_run,
    }


def run_validate(args: argparse.Namespace) -> Dict[str, object]:
    from omnispatial import api

    report = api.validate(args.bundle, output_format=args.format)
    report_path = None
    if args.report_dir:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        report_path = args.report_dir / f"{Path(args.bundle).stem}.validation.json"
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return {
        "task": "validate",
        "bundle": str(args.bundle),
        "format": args.format,
        "issue_count": len(report.issues),
        "ok": report.ok,
        "report_path": str(report_path) if report_path else None,
    }


def run_command(args: argparse.Namespace) -> Dict[str, object]:
    env = os.environ.copy()
    if args.env:
        for assignment in args.env:
            key, _, value = assignment.partition("=")
            env[key] = value
    print(f"Executing: {args.command}")
    start = time.time()
    completed = subprocess.run(shlex.split(args.command), check=True, env=env)  # noqa: S603  # nosec B603
    duration = time.time() - start
    return {
        "task": "command",
        "command": args.command,
        "returncode": completed.returncode,
        "duration_override_s": duration,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Optional path to write JSON metrics.")
    parser.add_argument("--label", default="benchmark", help="Label used in reports and summaries.")
    default_hw = platform.uname().machine
    parser.add_argument("--hardware", default=default_hw, help="Hardware descriptor to annotate results.")
    parser.add_argument("--interval", type=float, default=0.5, help="Sampling interval in seconds (default: 0.5).")

    subparsers = parser.add_subparsers(dest="mode", required=True)

    convert = subparsers.add_parser("convert", help="Profile an OmniSpatial conversion run.")
    convert.add_argument("input", type=Path, help="Input dataset path for conversion.")
    convert.add_argument("out", type=Path, help="Output path for converted bundle.")
    convert.add_argument("--vendor", help="Adapter to force when converting.")
    convert.add_argument("--format", default="ngff", choices=["ngff", "spatialdata"], help="Output format.")
    convert.add_argument("--dry-run", action="store_true", help="Detect adapter without writing output.")
    convert.add_argument("--image-chunks", help="Image chunk size (comma-separated).")
    convert.add_argument("--label-chunks", help="Label chunk size (comma-separated).")
    convert.add_argument("--compressor", default="zstd", help="Compressor name for NGFF outputs.")
    convert.add_argument("--compression-level", type=int, default=5, help="Compressor level for NGFF outputs.")

    validate = subparsers.add_parser("validate", help="Profile bundle validation.")
    validate.add_argument("bundle", type=Path, help="Bundle path for validation benchmark.")
    validate.add_argument("--format", default="ngff", choices=["ngff", "spatialdata"], help="Bundle format for validation.")
    validate.add_argument("--report-dir", type=Path, help="Optional directory to dump validation JSON output.")

    command = subparsers.add_parser("command", help="Profile an arbitrary shell command.")
    command.add_argument("command", help="Command to execute under profiling.")
    command.add_argument("--env", action="append", help="Environment variable assignment KEY=VALUE (repeatable).")

    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.mode == "convert":
        if args.input is None or args.out is None:
            raise SystemExit("convert mode requires positional arguments: input and out.")
    elif args.mode == "validate":
        if args.bundle is None:
            raise SystemExit("--bundle is required for validate mode.")
    elif args.mode == "command":
        if not args.command:
            raise SystemExit("--command must be provided for command mode.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    validate_args(args)

    metadata: Dict[str, object] = {
        "mode": args.mode,
        "label": args.label,
        "hardware": args.hardware,
        "timestamp": time.time(),
    }

    with ProfileSession(label=args.label, interval=args.interval) as session:
        if args.mode == "convert":
            metadata.update(run_convert(args))
        elif args.mode == "validate":
            metadata.update(run_validate(args))
        else:
            metadata.update(run_command(args))

    print(json.dumps(session.summary, indent=2))
    if args.report:
        session.emit(args.report, metadata)
        print(f"Wrote report to {args.report}")


if __name__ == "__main__":
    main()
