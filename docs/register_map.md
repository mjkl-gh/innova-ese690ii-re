# Innova ESE690II — Modbus Register Map

> Last updated: 2026-08-09  
> Source scan: `scan_20260809_210442.csv`  
> Address base: 0-based PDU / Modbus Poll style  
> Scope: documented registers + latest scan values

---

## Rule

No remap claims, no guesses. If a register is in the doc, it stays in its documented address.

---

## Rev.01 documented registers

| Addr | Name | Description | Scale / unit | R/W | Latest scan value | Notes |
|------|------|-------------|-------------|-----|------------------|-------|
| 0 | T1 / T_AIR | Room air temperature | x0.1 °C | R | 277 | 27.7 °C |
| 1 | T2 / H2 | Hot-water temperature probe | x0.1 °C | R | 65026 | sentinel / probe absent |
| 2 | T3 / H4 | Cold-water temperature probe | x0.1 °C | R | 1209 | latest scan raw value |
| 8 | SP | Real setpoint | x0.1 °C | R | 300 | 30.0 °C |
| 9 | OUT | Output relays | flags | R | 9 | EV1 + BOILER |
| 15 | MOT_SET | Motor speed setpoint | RPM | R | 1500 | 1500 RPM |
| 104 | STAT | Unit status flags | flags | R | 8194 | heating active; H4 absent |
| 105 | ALR_STAT | Alarm flags | flags | R | 1209 | 0x04B9 |
| 200 | ADR | Modbus slave address | 1 | R/W | 1 | documented address |
| 201 | PRG | Program / mode | flags | R/W | 3 | documented address |
| 202 | SPL | Minimum setpoint | x0.1 °C | R/W | 160 | documented address |
| 203 | SPH | Maximum setpoint | x0.1 °C | R/W | 280 | documented address |
| 209 | E_SAVING | Presence-contact offset / standby | x0.1 K | R/W | 0 | documented address |
| 210 | MVV5 | Minimum speed in MIN/Night | RPM | R/W | 400 | documented address |
| 211 | MVV4 | Max in Night / min in AUTO | RPM | R/W | 550 | documented address |
| 212 | MVV3 | Max in MIN / min in MAX | RPM | R/W | 680 | documented address |
| 213 | MVV2 | Max in AUTO | RPM | R/W | 1100 | documented address |
| 214 | MVV1 | Max in MAX | RPM | R/W | 1500 | documented address |
| 218 | LLO | Min water temp for heating | x0.1 °C | R/W | 300 | documented address |
| 219 | LHI | Max water temp for cooling | x0.1 °C | R/W | 200 | documented address |
| 221 | ACL | Maintenance frequency | hours | R/W | 0 | documented address |
| 222 | ACL_TIM | Fan working hours counter | hours | R/W | 0 | documented address |
| 230 | MVVP3 | Performance-mode speed limit | RPM | R/W | 720 | documented address |
| 231 | SP | Absolute setpoint | x0.1 °C | R/W | 300 | documented address |
| 233 | Man | Seasonal auto/manual | flags | R/W | 0 | documented address |
| 234 | MVVP2 | Performance-mode AUTO limit | RPM | R/W | 1220 | documented address |
| 242 | OS1 | T1 probe offset | x0.1 K | R/W | 0 | documented address |
| 243 | OS2 | H2 probe offset | x0.1 K | R/W | 0 | documented address |
| 244 | OS3 | H4 probe offset | x0.1 K | R/W | 0 | documented address |
| 245 | SPL_W | WEB minimum setpoint | x0.1 °C | R/W | 200 | documented address |
| 246 | SPH_W | WEB maximum setpoint | x0.1 °C | R/W | 240 | documented address |
| 247 | WEB | Webserver flags | flags | R/W | 0 | documented address |

### STAT / ALR_STAT

- `STAT = 8194 (0x2002)`
  - bit 1 = heating active
  - bit 13 = H4 probe absent
- `ALR_STAT = 1209 (0x04B9)`
  - repeated raw value in this scan

---

## FC06 write-probe results

Targeted bit-by-bit write probing was run only on holding registers that were readable in the latest scan, with register `200` explicitly skipped.
Each probe used `0x01`, `0x02`, `0x04`, ... and restored the original value after each test.

| Addr | Latest scan value | Writable bits | Notes |
|------|------------------:|--------------|-------|
| 1 | 65026 | bit0 | write-probe confirmed |
| 2 | 1209 | bit11 | write-probe confirmed |
| 4 | 31 | bit3 | write-probe confirmed |
| 6 | 64516 | bit13 | write-probe confirmed |
| 7 | 64516 | bit10, bit11, bit14 | write-probe confirmed |
| 11 | 10004 | bit4 | write-probe confirmed |
| 12 | 10003 | bit4 | write-probe confirmed |
| 16 | 4095 | bit5 | write-probe confirmed |

---

## M7-PU documented registers

| Addr | Name | Description | Latest scan value | Scan status |
|------|------|-------------|------------------|-------------|
| 100 | REM_MODE | Remote work mode | n/a | read exception |
| 101 | REM_SET | Remote air setpoint | 0 | readable |
| 102 | REM_TA | Remote air temperature | 0 | readable |
| 550 | ADR | Modbus slave address | n/a | read exception |
| 552 | CFG | Config flags | n/a | read exception |

---

## Other readable scan values

These are from the latest scan but are not yet documented by the PDFs.

| Addr | Value |
|------|------:|
| 3 | 15 |
| 4 | 31 |
| 5 | 554 |
| 6 | 64516 |
| 7 | 64516 |
| 10 | 2917 |
| 11 | 10004 |
| 12 | 10003 |
| 13 | 1209 |
| 14 | 4095 |
| 16 | 4095 |
| 17 | 299 |
| 18 | 277 |
| 19 | 0 |
| 21 | 1 |
| 22 | 0 |
| 24 | 1209 |
| 35 | 1209 |
| 46 | 1209 |
| 55 | 1209 |
| 61 | 1209 |
| 83 | 1209 |
| 94 | 1209 |
| 195 | 98 |
| 196 | 0 |
| 197 | 0 |
| 198 | 17 |
| 199 | 1209 |
| 204 | 1209 |
| 205 | 0 |
| 206 | 20 |
| 207 | 65516 |
| 208 | 300 |
| 215 | 1209 |
| 220 | 15 |
| 225 | 65444 |
| 226 | 1209 |
| 227 | 1 |
| 228 | 700 |
| 229 | 350 |
| 232 | 50 |
| 235 | 4 |
| 236 | 1 |
| 239 | 65531 |
| 240 | 65534 |
| 241 | 5 |
| 248 | 1209 |
| 249 | 30 |
| 250 | 0 |
| 255 | 1 |
| 256 | 0 |
| 257 | 0 |
| 258 | 0 |
| 259 | 1209 |
| 260 | 0 |
| 261 | 20 |
| 262 | 65516 |
| 263 | 25 |
| 264 | 30 |
| 265 | 40 |
| 266 | 65 |
| 267 | 90 |
| 268 | 100 |
| 269 | 55 |
| 271 | 0 |
| 272 | 300 |
| 273 | 0 |
| 274 | 0 |
| 275 | 500 |
| 276 | 30 |
| 277 | 5 |
| 290 | 0 |
| 293 | 2 |
| 294 | 15 |
| 304 | 1 |
| 305 | 50 |
| 600 | 0 |
| 601 | 1 |
| 602 | 1 |
| 603 | 1 |
| 700 | 1 |
| 701 | 1 |
| 702 | 0 |
| 704 | 0 |
| 705 | 0 |
| 707 | 0 |
| 800 | 0 |
| 801 | 0 |
| 802 | 0 |
| 807 | 0 |
| 998 | 0 |
| 999 | 0 |
| 1004 | 1209 |
| 1050 | 2 |
| 1051 | 0 |
| 1052 | 25 |
| 1053 | 0 |
| 1054 | 0 |
| 1055 | 1 |
| 1056 | 0 |
| 1057 | 1505 |
| 1058 | 0 |
| 1061 | 0 |
| 1100 | 0 |
| 1101 | 0 |
| 1102 | 0 |
| 1104 | 0 |
| 1105 | 0 |
| 1106 | 0 |
| 1107 | 0 |
| 1150 | 1500 |
| 1151 | 1500 |
| 2000 | 0 |

---

## Notes

- The earlier remap idea is gone. The scan shows the documented Rev.01 registers at their documented addresses.
- `1209` (`0x04B9`) repeats across many addresses and still needs decoding.
- `65026`, `64516`, `65516`, `65531`, `65534`, and `65444` look like sentinel values.
- Write-probe results above are bitwise FC06 tests only; they do not imply the full 16-bit register is safe to write.
