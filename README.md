# Innova ESE690II Fancoil Controller — Reverse Engineering

Community reverse engineering of the **Innova ESE690II** fancoil controller board.

> ⚠️ **Work in progress.** Register map is incomplete. Contributions welcome.

---

## Hardware

| Item | Details |
|------|---------|
| Board | Innova ESE690II |
| Protocol | Modbus RTU (RS-485) — ASCII mode may also be supported |
| Baud rate | 9600 (default, may be configurable) |
| Parity | Even |
| Data bits | 8 |
| Stop bits | 1 |
| Default slave address | 1 |

### RS-485 Wiring

```
Controller board         Adapter
  [A / D+] ──────────── A / D+
  [B / D-] ──────────── B / D-
  [GND]    ──────────── GND (recommended)
```

Use a USB–RS-485 adapter (e.g. CH340/FTDI based) or an ESP32/ESP8266 with a MAX485 transceiver.

---

## Repository Layout

```
.
├── esphome/
│   └── innova_ese690ii.yaml     # ESPHome Modbus integration
├── tools/
│   └── scan_registers.py        # Register scanner (serial/TCP, RTU + ASCII)
├── docs/
│   └── register_map.md          # Known register map (community maintained)
└── requirements.txt
```

---

## Register Map

See [`docs/register_map.md`](docs/register_map.md) for the current state of the known register map.

---

## Tools

### `tools/scan_registers.py`

Scans the full Modbus register space and logs responses.
For *unknown* registers it performs a non-destructive bit-by-bit write probe
to determine writability and bit width.

```bash
pip install -r requirements.txt

# RTU over serial
python tools/scan_registers.py --transport serial --port /dev/ttyUSB0 --mode rtu --slave 1

# ASCII over serial
python tools/scan_registers.py --transport serial --port /dev/ttyUSB0 --mode ascii --slave 1

# RTU over TCP
python tools/scan_registers.py --transport tcp --host 192.168.1.50 --mode rtu --slave 1

# ASCII over TCP
python tools/scan_registers.py --transport tcp --host 192.168.1.50 --mode ascii --slave 1

# Limit to holding registers, addresses 0–99
python tools/scan_registers.py --transport serial --port /dev/ttyUSB0 --mode rtu \
    --reg-types holding --start 0 --end 99

# Skip write probing (read-only scan)
python tools/scan_registers.py --transport serial --port /dev/ttyUSB0 --mode rtu --no-write
```

Output is written to `scan_<timestamp>.csv` and `scan_<timestamp>.log`.

Use `--host` and optional `--tcp-port` for Ethernet/RS-485 gateways. `--mode rtu` with
`--transport tcp` gives RTU-over-TCP, while `--mode ascii` with `--transport tcp` gives
ASCII-over-TCP.

---

## ESPHome

Flash `esphome/innova_ese690ii.yaml` to an ESP32/ESP8266 connected via MAX485 to the controller.

Edit the substitutions block at the top of the file to match your network and hardware:

```yaml
substitutions:
  device_name: innova-fancoil
  modbus_id: innova_modbus
  slave_address: "1"
  uart_tx_pin: GPIO17
  uart_rx_pin: GPIO16
  uart_baud_rate: "9600"
```

---

## Contributing

1. Run the scanner against your unit and attach the CSV output to an issue.
2. If you identify a register, open a PR updating `docs/register_map.md` and the ESPHome YAML.

---

## License

MIT
