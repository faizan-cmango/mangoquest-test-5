// Module  : counter4d            File: counter4d.sv
// Project : counter4d            SAD : 3.1          Risk: LOW
// REQ-IDs : REQ-3.1.1, REQ-3.1.2, REQ-3.1.3, REQ-3.1.4, REQ-3.1.5, REQ-3.1.6
// Author  : Kemi, rev 1
// PURPOSE : 4-bit up-counter with enable and synchronous active-low reset, one clock domain.
// DEBUG NOTES : probe in this order: rst_n, en, cnt_value_next, cnt_value_ff, count;
//               waveform recipe: add wave cnt_*
// KNOWN GOTCHAS : reset is synchronous (clocks.yaml), so count clears only at a rising clk edge.
// PREFIXES: cnt
// nosplit: fewer than three control states, no FSM, one register
`default_nettype none
`timescale 1ns/1ps

module counter4d (
    input  wire logic       clk,    // REQ-3.1.6
    input  wire logic       rst_n,  // REQ-3.1.1, REQ-3.1.5
    input  wire logic       en,     // REQ-3.1.2, REQ-3.1.3, REQ-3.1.4
    output logic      [3:0] count   // REQ-3.1.2, REQ-3.1.3, REQ-3.1.4
);

  // -- C · DECLARATIONS — SAD 3.1 ---------------------------------------------------------
  logic [3:0] cnt_value_ff;    // REQ-3.1.1, REQ-3.1.2, REQ-3.1.3, REQ-3.1.4, REQ-3.1.5
  logic [3:0] cnt_value_next;  // REQ-3.1.2, REQ-3.1.3, REQ-3.1.4

  // -- D · COMBINATIONAL — SAD 3.1 --------------------------------------------------------
  // .. cnt : increment with natural 4-bit wrap, or hold — REQ-3.1.2, REQ-3.1.3, REQ-3.1.4
  assign cnt_value_next = en ? (cnt_value_ff + 4'd1) : cnt_value_ff;

  // -- E · SEQUENTIAL — SAD 3.1 -----------------------------------------------------------
  // .. cnt : counter value, reset has priority over en — REQ-3.1.1, REQ-3.1.5, REQ-3.1.6
  always_ff @(posedge clk) begin
    if (!rst_n) begin
      cnt_value_ff <= '0;
    end else begin
      cnt_value_ff <= cnt_value_next;
    end
  end

  // -- F · ASSERTIONS AND DEBUG HOOKS — SAD 3.1 -------------------------------------------
`ifndef SYNTHESIS
  always @(posedge clk) begin
    if (rst_n) begin
      assert (!$isunknown(cnt_value_ff)) else $error("a_cnt_value_known");
    end
  end
`endif

  // -- G · OUTPUTS — SAD 3.1 --------------------------------------------------------------
  assign count = cnt_value_ff;  // REQ-3.1.2, REQ-3.1.3, REQ-3.1.4

endmodule

`default_nettype wire
