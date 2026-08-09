#!/usr/bin/env python3
"""
Innova ESE690II — Modbus Register Scanner
==========================================

Scans all four Modbus register spaces and logs responses.
For unknown / unconfirmed writable registers it performs a non-destructive
bit-by-bit write probe to characterise the register width and writability.

Modes
-----
  Serial + RTU   : standard binary Modbus over RS-485
  Serial + ASCII : Modbus ASCII framing over RS-485 (some Innova firmware variants)
  TCP + RTU      : RTU-over-TCP via an Ethernet/serial gateway
  TCP + ASCII    : ASCII-over-TCP via an Ethernet/serial gateway

Usage
-----
  python scan_registers.py --port /dev/ttyUSB0 --transport serial --mode rtu   --slave 1
  python scan_registers.py --port /dev/ttyUSB0 --transport serial --mode ascii --slave 1

  # RTU-over-TCP
  python scan_registers.py --transport tcp --host 192.168.1.50 --mode rtu --slave 1

  # ASCII-over-TCP
  python scan_registers.py --transport tcp --host 192.168.1.50 --mode ascii --slave 1

  # Restrict to holding registers, addresses 0-49, skip write probing
  python scan_registers.py --transport serial --port /dev/ttyUSB0 --mode rtu \\
      --reg-types holding --start 0 --end 49

Output
------
  scan_<timestamp>.csv   : machine-readable register dump
  scan_<timestamp>.log   : human-readable annotated log
"""

from __future__ import annotations

import argparse
import csv
import inspect
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REG_TYPES = ("coil", "discrete", "input", "holding")

FC_NAMES = {
    "coil":     ("Read Coils (FC01)",            "Write Single Coil (FC05)"),
    "discrete": ("Read Discrete Inputs (FC02)",  None),
    "input":    ("Read Input Registers (FC04)",  None),
    "holding":  ("Read Holding Registers (FC03)", "Write Single Register (FC06)"),
}

MAX_COIL_ADDR     = 9999
MAX_DISCRETE_ADDR = 9999
MAX_REG_ADDR      = 9999


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RegisterResult:
    reg_type:      str
    address:       int
    raw_value:     Optional[int | bool]
    readable:      bool
    error:         Optional[str] = None

    # Write-probe results (only for holding / coil)
    write_probed:  bool = False
    writable_bits: list[int] = field(default_factory=list)  # bit positions that accepted a write
    write_error:   Optional[str] = None

    def csv_row(self) -> dict:
        return {
            "reg_type":      self.reg_type,
            "address":       self.address,
            "raw_value":     "" if self.raw_value is None else self.raw_value,
            "readable":      self.readable,
            "error":         self.error or "",
            "write_probed":  self.write_probed,
            "writable_bits": ",".join(str(b) for b in self.writable_bits),
            "write_error":   self.write_error or "",
        }

    CSV_FIELDS = [
        "reg_type", "address", "raw_value", "readable",
        "error", "write_probed", "writable_bits", "write_error",
    ]


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class InnovaScanner:
    def __init__(
        self,
        transport: str,
        mode: str,
        slave: int,
        port: Optional[str],
        host: Optional[str],
        tcp_port: int,
        baud: int,
        parity: str,
        timeout: float,
        inter_request_delay: float,
        probe_write: bool,
    ) -> None:
        self.slave = slave
        self.probe_write = probe_write
        self.inter_request_delay = inter_request_delay
        self.transport = transport
        self.mode = mode

        if transport == "serial":
            if not port:
                raise ValueError("Serial transport requires --port")
            self.endpoint = port
            self.client = ModbusSerialClient(
                port=port,
                framer=mode,
                baudrate=baud,
                parity=parity,
                bytesize=8,
                stopbits=1,
                timeout=timeout,
            )
        elif transport == "tcp":
            if not host:
                raise ValueError("TCP transport requires --host")
            self.endpoint = f"{host}:{tcp_port}"
            self.client = ModbusTcpClient(
                host=host,
                port=tcp_port,
                framer=mode,
                timeout=timeout,
            )
        else:
            raise ValueError(f"Unsupported transport: {transport}")

        self.request_unit_kwarg = self._detect_unit_kwarg()

        self.log = logging.getLogger("scanner")

    def _detect_unit_kwarg(self) -> str:
        methods = [
            self.client.read_coils,
            self.client.read_discrete_inputs,
            self.client.read_input_registers,
            self.client.read_holding_registers,
            self.client.write_coil,
            self.client.write_register,
        ]
        for method in methods:
            try:
                params = inspect.signature(method).parameters
            except (TypeError, ValueError):
                continue
            if "device_id" in params:
                return "device_id"
            if "slave" in params:
                return "slave"
        return "slave"

    def _unit_kwargs(self) -> dict[str, int]:
        return {self.request_unit_kwarg: self.slave}

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #

    def connect(self) -> None:
        if not self.client.connect():
            raise ConnectionError(f"Could not connect to {self.transport} endpoint {self.endpoint}")
        self.log.info(
            "Connected to %s endpoint %s using %s framing",
            self.transport,
            self.endpoint,
            self.mode,
        )

    def disconnect(self) -> None:
        self.client.close()
        self.log.info("Disconnected")

    # ------------------------------------------------------------------ #
    # Generic read helpers
    # ------------------------------------------------------------------ #

    def _sleep(self) -> None:
        if self.inter_request_delay > 0:
            time.sleep(self.inter_request_delay)

    def _read_coils(self, address: int) -> RegisterResult:
        self._sleep()
        rr = self.client.read_coils(address, count=1, **self._unit_kwargs())
        if rr.isError() or isinstance(rr, ExceptionResponse):
            return RegisterResult("coil", address, None, False, str(rr))
        return RegisterResult("coil", address, int(rr.bits[0]), True)

    def _read_discrete(self, address: int) -> RegisterResult:
        self._sleep()
        rr = self.client.read_discrete_inputs(address, count=1, **self._unit_kwargs())
        if rr.isError() or isinstance(rr, ExceptionResponse):
            return RegisterResult("discrete", address, None, False, str(rr))
        return RegisterResult("discrete", address, int(rr.bits[0]), True)

    def _read_input(self, address: int) -> RegisterResult:
        self._sleep()
        rr = self.client.read_input_registers(address, count=1, **self._unit_kwargs())
        if rr.isError() or isinstance(rr, ExceptionResponse):
            return RegisterResult("input", address, None, False, str(rr))
        return RegisterResult("input", address, rr.registers[0], True)

    def _read_holding(self, address: int) -> RegisterResult:
        self._sleep()
        rr = self.client.read_holding_registers(address, count=1, **self._unit_kwargs())
        if rr.isError() or isinstance(rr, ExceptionResponse):
            return RegisterResult("holding", address, None, False, str(rr))
        return RegisterResult("holding", address, rr.registers[0], True)

    # ------------------------------------------------------------------ #
    # Write-probe helpers
    # ------------------------------------------------------------------ #

    def _probe_holding_register(self, result: RegisterResult) -> None:
        """
        Non-destructive bit probe for a holding register.

        Strategy:
          1. Read current value (baseline).
          2. For each bit position 0–15:
             a. Write (baseline XOR (1 << bit)).
             b. Read back.
             c. If the returned value matches the toggled value, the bit is writable.
             d. Restore baseline regardless.
          3. After all bits, restore original value.

        The restoration write means the net effect on the device is zero
        *if* the register is idempotent.  Skip known actuator registers.
        """
        baseline = result.raw_value
        writable_bits: list[int] = []

        for bit in range(16):
            toggled = baseline ^ (1 << bit)
            self._sleep()
            wr = self.client.write_register(result.address, toggled, **self._unit_kwargs())

            if wr.isError() or isinstance(wr, ExceptionResponse):
                # Write rejected by device — not writable at this bit (or at all)
                self._sleep()
                self.client.write_register(result.address, baseline, **self._unit_kwargs())
                continue

            # Read back to verify
            self._sleep()
            rr = self.client.read_holding_registers(result.address, count=1, **self._unit_kwargs())
            read_back = rr.registers[0] if not rr.isError() else None

            # Restore
            self._sleep()
            self.client.write_register(result.address, baseline, **self._unit_kwargs())

            if read_back is not None and (read_back & (1 << bit)) == (toggled & (1 << bit)):
                writable_bits.append(bit)

        result.write_probed  = True
        result.writable_bits = writable_bits
        if not writable_bits:
            result.write_error = "no writable bits detected"

    def _probe_coil(self, result: RegisterResult) -> None:
        """Toggle a coil and restore it."""
        baseline = bool(result.raw_value)
        toggled  = not baseline
        self._sleep()
        wr = self.client.write_coil(result.address, toggled, **self._unit_kwargs())

        if wr.isError() or isinstance(wr, ExceptionResponse):
            result.write_probed = True
            result.write_error  = str(wr)
            return

        # Read back
        self._sleep()
        rr = self.client.read_coils(result.address, count=1, **self._unit_kwargs())
        read_back = rr.bits[0] if not rr.isError() else None

        # Restore
        self._sleep()
        self.client.write_coil(result.address, baseline, **self._unit_kwargs())

        result.write_probed = True
        if read_back is not None and read_back == toggled:
            result.writable_bits = [0]   # coil = bit 0
        else:
            result.write_error = "write did not persist"

    # ------------------------------------------------------------------ #
    # Scan a range
    # ------------------------------------------------------------------ #

    def scan_range(
        self,
        reg_type: str,
        start: int,
        end: int,
    ) -> Iterable[RegisterResult]:
        self.log.info("Scanning %s registers %d–%d", reg_type, start, end)

        for addr in range(start, end + 1):
            result: RegisterResult

            if reg_type == "coil":
                result = self._read_coils(addr)
            elif reg_type == "discrete":
                result = self._read_discrete(addr)
            elif reg_type == "input":
                result = self._read_input(addr)
            elif reg_type == "holding":
                result = self._read_holding(addr)
            else:
                raise ValueError(f"Unknown reg_type: {reg_type}")

            # Log read result
            if result.readable:
                self.log.debug(
                    "[%s @ %d] value=0x%04X (%d)",
                    reg_type, addr, result.raw_value, result.raw_value,
                )
            else:
                self.log.debug(
                    "[%s @ %d] READ ERROR: %s",
                    reg_type, addr, result.error,
                )

            # Write probe
            if self.probe_write and result.readable:
                if reg_type == "holding":
                    self._probe_holding_register(result)
                elif reg_type == "coil":
                    self._probe_coil(result)

                if result.write_probed:
                    if result.writable_bits:
                        self.log.info(
                            "[%s @ %d] WRITABLE bits: %s",
                            reg_type, addr,
                            [f"bit{b}" for b in result.writable_bits],
                        )
                    else:
                        self.log.debug(
                            "[%s @ %d] not writable (%s)",
                            reg_type, addr, result.write_error,
                        )

            yield result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Innova ESE690II Modbus register scanner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--transport",
        default="serial",
        choices=["serial", "tcp"],
        help="Physical transport for the Modbus session",
    )
    p.add_argument("--port", help="Serial port, e.g. /dev/ttyUSB0 or COM3 (serial transport only)")
    p.add_argument("--host", help="Gateway/controller hostname or IP (TCP transport only)")
    p.add_argument("--tcp-port", type=int, default=502, help="TCP port for Modbus gateway/controller")
    p.add_argument("--mode",    default="rtu", choices=["rtu", "ascii"], help="Modbus framing mode")
    p.add_argument("--slave",   type=int, default=1, help="Modbus slave address")
    p.add_argument("--baud",    type=int, default=9600, help="Baud rate")
    p.add_argument("--parity",  default="E", choices=["N", "E", "O"], help="Serial parity")
    p.add_argument("--timeout", type=float, default=1.0, help="Request timeout in seconds")
    p.add_argument("--delay",   type=float, default=0.05,
                   help="Delay between requests in seconds (avoid bus flooding)")
    p.add_argument("--reg-types", nargs="+", default=list(REG_TYPES),
                   choices=list(REG_TYPES), metavar="TYPE",
                   help="Register types to scan: coil discrete input holding")
    p.add_argument("--start",   type=int, default=0,    help="First register address (0-based)")
    p.add_argument("--end",     type=int, default=99,   help="Last register address (0-based, inclusive)")
    p.add_argument("--write", action="store_true",
                   help="Enable write probing (bit-by-bit, restores original value)")
    p.add_argument("--output-dir", default=".", help="Directory for output files")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG logging")
    return p


def setup_logging(verbose: bool, log_path: Path) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt   = "%(asctime)s %(levelname)-7s %(message)s"

    logging.basicConfig(level=level, format=fmt, handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ])


def validate_args(args: argparse.Namespace) -> None:
    if args.transport == "serial" and not args.port:
        raise SystemExit("--port is required when --transport serial is used")
    if args.transport == "tcp" and not args.host:
        raise SystemExit("--host is required when --transport tcp is used")
    if args.start > args.end:
        raise SystemExit("--start must be less than or equal to --end")


def main() -> None:
    args = build_parser().parse_args()
    validate_args(args)
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    log_path = outdir / f"scan_{ts}.log"
    csv_path = outdir / f"scan_{ts}.csv"

    setup_logging(args.verbose, log_path)
    log = logging.getLogger("main")

    log.info("Innova ESE690II register scanner")
    if args.transport == "serial":
        endpoint = args.port
        transport_details = f"baud={args.baud} parity={args.parity}"
    else:
        endpoint = f"{args.host}:{args.tcp_port}"
        transport_details = "tcp"
    log.info("  transport=%s  endpoint=%s  mode=%s  slave=%d  %s",
             args.transport, endpoint, args.mode, args.slave, transport_details)
    log.info("  reg_types=%s  start=%d  end=%d  probe_write=%s",
             args.reg_types, args.start, args.end, args.write)

    scanner = InnovaScanner(
        transport=args.transport,
        mode=args.mode,
        slave=args.slave,
        port=args.port,
        host=args.host,
        tcp_port=args.tcp_port,
        baud=args.baud,
        parity=args.parity,
        timeout=args.timeout,
        inter_request_delay=args.delay,
        probe_write=args.write,
    )

    scanner.connect()

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RegisterResult.CSV_FIELDS)
            writer.writeheader()

            for reg_type in args.reg_types:
                for result in scanner.scan_range(reg_type, args.start, args.end):
                    writer.writerow(result.csv_row())

    except KeyboardInterrupt:
        log.warning("Interrupted by user")
    except ModbusException as exc:
        log.error("Modbus error: %s", exc)
        sys.exit(1)
    finally:
        scanner.disconnect()

    log.info("Done. Output: %s, %s", csv_path, log_path)


if __name__ == "__main__":
    main()
