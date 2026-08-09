# Innova ESE690II — Known Register Map

> Last updated: 2026-08  
> Protocol: Modbus RTU / ASCII  
> Default slave address: 1

Register addresses are **0-based** (PDU addresses).  
Add 1 for 1-based display addresses used by some tools (e.g. Modbus Poll).

## Legend

| Symbol | Meaning |
|--------|---------|
| R | Read only |
| R/W | Read / Write |
| ? | Unknown / unconfirmed |

---

## Holding Registers (function code 03 read / 06,16 write)

| Address (0-based) | Name | Unit | Scale | Access | Notes |
|-------------------|------|------|-------|--------|-------|
| — | — | — | — | — | *Not yet mapped — run scanner and contribute!* |

---

## Input Registers (function code 04)

| Address (0-based) | Name | Unit | Scale | Access | Notes |
|-------------------|------|------|-------|--------|-------|
| — | — | — | — | R | *Not yet mapped* |

---

## Coils (function code 01 read / 05 write)

| Address (0-based) | Name | Access | Notes |
|-------------------|------|--------|-------|
| — | — | — | *Not yet mapped* |

---

## Discrete Inputs (function code 02)

| Address (0-based) | Name | Access | Notes |
|-------------------|------|--------|-------|
| — | — | R | *Not yet mapped* |

---

## Notes

- Tested firmware version: unknown
- Reference scanner output files are in `docs/scans/` (add yours via PR)
