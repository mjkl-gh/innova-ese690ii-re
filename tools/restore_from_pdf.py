#!/usr/bin/env python3
"""
Innova ESE690II — Modbus Register Restore from PDF
===================================================

Parses a MODBUS Address Scan PDF (e.g. from a Fluke or similar tool) and
writes every readable holding register value back to the device at the same
address.  The PDF contains register ranges and their values in a grid.

The PDF format is:
  400000-400009              (address range: registers 0-9 in 0-based notation)
  Device ID: 1 Length: 999
  Point Type: [03: HOLDING REGISTER]
  +0                         (register offset within range)
  00275                      (value for first register)
  02934                      (value for second register)
  ...
  +1
  65026
  10004
  ...

Usage
-----
  # Dry-run
  python tools/restore_from_pdf.py "MODBUS Address Scan.pdf" --dry-run

  # RTU-over-TCP
  python tools/restore_from_pdf.py "MODBUS Address Scan.pdf" \\
      --transport tcp --host 192.168.0.7 --mode rtu --slave 1

  # Serial RTU
  python tools/restore_from_pdf.py "MODBUS Address Scan.pdf" \\
      --transport serial --port /dev/ttyUSB0 --mode rtu --slave 1
"""

from __future__ import annotations

import argparse
import inspect
import logging
import re
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse


# ---------------------------------------------------------------------------
# PDF Parsing
# ---------------------------------------------------------------------------

def _parse_pdf(pdf_path: Path) -> dict[int, int]:
    """Parse MODBUS Address Scan PDF and return {address: value} dict.
    
    Format: each line has address range and 10 values:
        400000-400009 00275 65026 65026 00015 00031 00550 64516 64516 00300 00009
        400010-400019 02934 10004 10003 01202 04095 01500 04095 00300 00275 00000
        400100-400109 - 00000 00000 00000 08194 00000 00000 00000 00000 00000
    """
    if pdfplumber is None:
        raise ImportError("pdfplumber is required: pip install pdfplumber")

    registers = {}

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    for line in full_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Look for address range like "400000-400009 value1 value2 ..."
        # Matches 400XXX-400YYY format where XXX and YYY are 0-999
        match = re.match(r"^400(\d{3})-400(\d{3})\s+(.*)$", line)
        if match:
            start_addr = int(match.group(1))
            values_str = match.group(3)

            # Parse the values (space-separated, "-" means empty/unreadable)
            values = values_str.split()
            for i, val_str in enumerate(values):
                if val_str == "-":
                    continue
                try:
                    value = int(val_str)
                    address = start_addr + i
                    registers[address] = value
                except ValueError:
                    pass

    return registers


# ---------------------------------------------------------------------------
# Modbus Helpers
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description="Restore holding registers from MODBUS Address Scan PDF back to the device."
    )

    p.add_argument("pdf", type=Path, help="MODBUS Address Scan PDF")
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

    # Parse PDF
    if not args.pdf.exists():
        log.error("PDF not found: %s", args.pdf)
        sys.exit(1)

    try:
        registers = _parse_pdf(args.pdf)
    except ImportError as e:
        log.error("Cannot parse PDF: %s. Install with: pip install pdfplumber", e)
        sys.exit(1)
    except Exception as e:
        log.error("Failed to parse PDF: %s", e)
        sys.exit(1)

    if not registers:
        log.error("No holding registers found in %s", args.pdf)
        sys.exit(1)

    skip_set = set(args.skip)
    entries_to_write = [
        {"address": addr, "value": val}
        for addr, val in sorted(registers.items())
        if addr not in skip_set
    ]
    skipped = [
        {"address": addr, "value": val}
        for addr, val in sorted(registers.items())
        if addr in skip_set
    ]

    log.info("Parsed %d holding register(s) from %s", len(registers), args.pdf)
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
