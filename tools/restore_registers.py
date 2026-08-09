#!/usr/bin/env python3
"""
Innova ESE690II — Modbus Register Restore
==========================================

Reads a CSV produced by scan_registers.py and writes every readable holding-
register value back to the device at the same address.  Useful for restoring
known-good state after a write-probe session, or for verifying that a register
is still writable.

Only rows where:
  - reg_type  == "holding"
  - readable  == True
  - raw_value is a valid integer

are written.  All other rows are silently skipped.

Usage
-----
  # Dry-run (show what would be written, no actual writes)
  python tools/restore_registers.py scan_20260809_210103.csv --dry-run

  # RTU-over-TCP
  python tools/restore_registers.py scan_20260809_210103.csv \\
      --transport tcp --host 192.168.1.50 --mode rtu --slave 1

  # ASCII-over-TCP
  python tools/restore_registers.py scan_20260809_210103.csv \\
      --transport tcp --host 192.168.1.50 --mode ascii --slave 1

  # Serial RTU
  python tools/restore_registers.py scan_20260809_210103.csv \\
      --transport serial --port /dev/ttyUSB0 --mode rtu --slave 1
"""

from __future__ import annotations

import argparse
import csv
import inspect
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_unit_kwarg(client) -> str:
    for method in (client.write_register,):
        try:
            params = inspect.signature(method).parameters
        except (TypeError, ValueError):
            continue
        if "device_id" in params:
            return "device_id"
        if "slave" in params:
            return "slave"
    return "slave"


def _build_client(args: argparse.Namespace):
    if args.transport == "serial":
        if not args.port:
            raise ValueError("Serial transport requires --port")
        return ModbusSerialClient(
            port=args.port,
            framer=args.mode,
            baudrate=args.baud,
            parity=args.parity,
            bytesize=8,
            stopbits=1,
            timeout=args.timeout,
        )
    elif args.transport == "tcp":
        if not args.host:
            raise ValueError("TCP transport requires --host")
        return ModbusTcpClient(
            host=args.host,
            port=args.tcp_port,
            framer=args.mode,
            timeout=args.timeout,
        )
    else:
        raise ValueError(f"Unsupported transport: {args.transport}")


def _load_csv(path: Path) -> list[dict]:
    """Return rows from the CSV that are writable holding registers."""
    entries = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("reg_type") != "holding":
                continue
            if row.get("readable", "").strip().lower() != "true":
                continue
            raw = row.get("raw_value", "").strip()
            try:
                value = int(raw)
            except (ValueError, TypeError):
                continue
            entries.append({"address": int(row["address"]), "value": value})
    return entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description="Restore holding registers from a scan CSV back to the device."
    )

    p.add_argument("csv", type=Path, help="Scan CSV produced by scan_registers.py")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be written without sending any Modbus frames")

    # Transport
    p.add_argument("--transport", choices=["serial", "tcp"], default="tcp")
    p.add_argument("--mode",      choices=["rtu", "ascii"],  default="rtu",
                   help="Modbus framing mode")
    p.add_argument("--host",     default="192.168.0.7",
                   help="Host/IP for TCP transport")
    p.add_argument("--tcp-port", type=int, default=1963,
                   help="TCP port (default 1963)")
    p.add_argument("--port",     default="/dev/ttyUSB0",
                   help="Serial device (e.g. /dev/ttyUSB0)")
    p.add_argument("--baud",     type=int, default=9600)
    p.add_argument("--parity",   default="N")
    p.add_argument("--timeout",  type=float, default=1.0)
    p.add_argument("--slave",    type=int,   default=1,
                   help="Modbus slave/unit ID")
    p.add_argument("--delay",    type=float, default=0.1,
                   help="Delay between requests in seconds (default 0.1)")
    p.add_argument("--skip",     type=int,   nargs="*", default=[],
                   help="Addresses to skip (space-separated, e.g. --skip 200 201)")
    p.add_argument("--no-verify", action="store_true",
                   help="Skip read-back verification after each write (faster but less safe)")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="Reduce output to INFO level (default is DEBUG)")

    args = p.parse_args()

    # Logging
    log_level = logging.INFO if args.quiet else logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    log = logging.getLogger("restore")

    # Load CSV
    if not args.csv.exists():
        log.error("CSV not found: %s", args.csv)
        sys.exit(1)

    entries = _load_csv(args.csv)
    if not entries:
        log.error("No writable holding registers found in %s", args.csv)
        sys.exit(1)

    skip_set = set(args.skip)
    entries_to_write = [e for e in entries if e["address"] not in skip_set]
    skipped = [e for e in entries if e["address"] in skip_set]

    log.info("Loaded %d holding register(s) from %s", len(entries), args.csv)
    if skipped:
        log.info("Skipping %d address(es): %s", len(skipped),
                 [e["address"] for e in skipped])
    log.info("Will write %d register(s)", len(entries_to_write))

    if args.dry_run:
        log.info("--- DRY RUN (no actual writes) ---")
        for e in entries_to_write:
            log.info("  [holding @ %d] would write 0x%04X (%d)",
                     e["address"], e["value"], e["value"])
        log.info("Dry run complete.")
        return

    # Build client
    client = _build_client(args)
    unit_kwarg = _detect_unit_kwarg(client)

    endpoint = (f"{args.host}:{args.tcp_port}" if args.transport == "tcp"
                else args.port)
    log.info("Connecting to %s endpoint %s using %s framing",
             args.transport, endpoint, args.mode)

    if not client.connect():
        log.error("Could not connect to %s endpoint %s", args.transport, endpoint)
        sys.exit(1)

    log.info("Connected")

    ok = 0
    fail = 0
    mismatch = 0

    try:
        for e in entries_to_write:
            addr, value = e["address"], e["value"]
            log.debug("[holding @ %d] writing 0x%04X (%d)…", addr, value, value)

            if args.delay > 0:
                time.sleep(args.delay)

            try:
                wr = client.write_register(addr, value, **{unit_kwarg: args.slave})
                if wr.isError() or isinstance(wr, ExceptionResponse):
                    log.warning("[holding @ %d] WRITE FAILED: %s", addr, wr)
                    fail += 1
                    continue

                # Read back to verify persistence
                if not args.no_verify:
                    if args.delay > 0:
                        time.sleep(args.delay)
                    rr = client.read_holding_registers(addr, count=1, **{unit_kwarg: args.slave})
                    if rr.isError() or isinstance(rr, ExceptionResponse):
                        log.warning("[holding @ %d] VERIFY FAILED (read error): %s", addr, rr)
                        fail += 1
                    elif rr.registers[0] == value:
                        log.info("[holding @ %d] OK  0x%04X (%d) [verified]", addr, value, value)
                        ok += 1
                    else:
                        read_back = rr.registers[0]
                        log.warning("[holding @ %d] MISMATCH: wrote 0x%04X (%d) but read back 0x%04X (%d)",
                                   addr, value, value, read_back, read_back)
                        mismatch += 1
                else:
                    log.info("[holding @ %d] OK  0x%04X (%d)", addr, value, value)
                    ok += 1

            except (ModbusException, Exception) as exc:
                log.warning("[holding @ %d] EXCEPTION: %s", addr, exc)
                fail += 1

    finally:
        client.close()
        log.info("Disconnected")

    log.info("Done — %d written, %d failed, %d mismatch", ok, fail, mismatch)
    if fail or mismatch:
        sys.exit(1)


if __name__ == "__main__":
    main()
