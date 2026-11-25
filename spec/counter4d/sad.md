# System Architecture Document — counter4d · SAD v0.1

> Machine index: `sad.yaml`. Requirements live in `rtm.yaml`, ports in `idd/`, scenarios in
> `vps.yaml`, risk in `riskmap.yaml`, clocks in `clocks.yaml`.

## 1 Scope and context
counter4d is a 4-bit synchronous up-counter with enable and synchronous active-low reset, in one clock domain (clocks.yaml). Interface: IDD-COUNT_IF.

Out of scope: registers or bus interfaces, interrupts, clock domain crossings, power management, memories, clock gating. Scan ports are added by DFT insertion and are not in the interface.

Assumptions (the brief is final; defaults recorded in decisions.yaml): no area target (ADR-02); DFT as a note, not a document (ADR-03); IDD protocol class `level` for plain pins (ADR-01); BRS currents and the 1.8 V LDO gap (ADR-04).

Verification harness rules: inputs change only at falling clock edges, never in the timestep of a rising edge; clock starts low; the same harness runs unchanged on the gate-level netlist; a failing regression is reproduced with a single-seed run and fixed before the full batch is rerun.

## 2 Block decomposition
One block, counter4d. Nothing to partition.

## 3.1 Counting function — REQ-3.1.1 … REQ-3.1.6
At each rising clk edge: rst_n 0 gives 0 (REQ-3.1.1, REQ-3.1.5, priority over en); otherwise en 1 increments with wrap 15 to 0 (REQ-3.1.2, REQ-3.1.3); en 0 holds (REQ-3.1.4). Output changes only on a rising edge (REQ-3.1.6).

```
clk   _/‾\_/‾\_/‾\_/‾\_
en    ___/‾‾‾‾‾‾‾‾\____   (driven at falling edges)
count  0   0  1  2  2
```

Construction: a 4-bit state, an incrementer and a reset/enable mux in front of it.

## 6 Performance power and area
Target frequency in clocks.yaml. Feasibility (proxy, opensta_liberty, confidence 0.5, pre-layout): fmax estimate 1257.9 MHz, area 140.1 um2, target met. No area or power target.

## 7 Risk register
See `riskmap.yaml`.

## 8 Open items
No open ArchChallenges. The chip and 1.8 V regulator Device Models and the parts snapshot are supplied by a person at board/counter4d_eval/ (see BRS-9).
