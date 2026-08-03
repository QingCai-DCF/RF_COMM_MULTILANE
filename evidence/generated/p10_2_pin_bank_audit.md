# P10.2 AX7020 pin/bank audit

- Status: `PASS`.
- 16 unique PL signal pins per endpoint; no package-pin collision.
- Banks 34/35 are both documented at 3.3 V; every selected signal uses LVCMOS33 and a 33-ohm connector series path.
- Lane0/lane1 are preserved. Lane2/lane3 are independently sourced from AX7020 J11, not a Z7010 XDC.
- H16/L16 clock capability and K14/M17/E18 auxiliary-analog capability are audited ordinary-GPIO uses, not hidden clock/XADC consumers.
- J10-26/U13 R29 and configuration/partial-power limitations remain explicitly recorded.
