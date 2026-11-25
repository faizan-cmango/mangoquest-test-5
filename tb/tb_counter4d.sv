// TC-001: reset clears a nonzero count and holds it at 0 (VPS-01, REQ-3.1.1)
// TC-002: hold: count unchanged while en is 0 (VPS-02, REQ-3.1.4)
// TC-003: increment by 1 per edge, changes only at a rising edge (VPS-03, REQ-3.1.2, REQ-3.1.6)
// TC-004: wrap from 15 to 0 (VPS-04, REQ-3.1.3)
// TC-005: reset priority over en (VPS-05, REQ-3.1.5)
// TC-006: reset-to-idle: every output at its reset value after reset (REQ-3.1.1)
// TC-007: no X after reset: no output is X or Z once reset is released (REQ-3.1.1)
// TC-008: no deadlock: count wraps to 0 within 16 cycles of enabling (REQ-3.1.3)
`default_nettype none
`timescale 1ns/1ps

module tb_counter4d;
  logic clk = 1'b0;
  logic rst_n = 1'b0;
  logic en = 1'b0;
  logic [3:0] count;

  integer cycle = 0;
  integer errors = 0;
  logic [3:0] exp_count;
  logic [3:0] held;

  counter4d dut (
      .clk  (clk),
      .rst_n(rst_n),
      .en   (en),
      .count(count)
  );

  always #5 clk = ~clk;
  always @(posedge clk) cycle <= cycle + 1;

  // Reference model, REQ-3.1.1..5
  always @(posedge clk) begin
    if (!rst_n) exp_count <= 4'd0;
    else if (en) exp_count <= exp_count + 4'd1;
  end

  task automatic check(input string signal, input logic [63:0] expected, input logic [63:0] actual);
    if (actual !== expected) begin
      errors = errors + 1;
      $display("MISMATCH cycle=%0d signal=%s expected=%0h actual=%0h", cycle, signal, expected,
               actual);
    end
  endtask

  // Inputs change only at falling edges; outputs are checked just before.
  task automatic apply(input logic r, input logic e);
    @(negedge clk);
    check("count", {60'd0, exp_count}, {60'd0, count});
    if ($isunknown(count)) begin
      errors = errors + 1;
      $display("MISMATCH cycle=%0d signal=count_x expected=known actual=%0h", cycle, count);
    end
    rst_n = r;
    en = e;
  endtask

  initial begin
    // TC-006: reset-to-idle (REQ-3.1.1)
    apply(1'b0, 1'b0);
    apply(1'b0, 1'b0);
    apply(1'b0, 1'b0);
    check("count", 64'd0, {60'd0, count});
    // TC-003 / TC-004 / TC-008: increment and wrap (REQ-3.1.2, REQ-3.1.3)
    repeat (16) apply(1'b1, 1'b1);
    @(negedge clk);
    check("count_wrap", 64'd0, {60'd0, count});
    repeat (5) apply(1'b1, 1'b1);
    // TC-002: hold (REQ-3.1.4)
    apply(1'b1, 1'b0);
    apply(1'b1, 1'b0);
    held = count;
    check("count_nonzero", 64'd1, {63'd0, held != 4'd0});
    repeat (4) apply(1'b1, 1'b0);
    @(negedge clk);
    check("count_hold", {60'd0, held}, {60'd0, count});
    // TC-001 / TC-005: reset priority over en (REQ-3.1.1, REQ-3.1.5)
    apply(1'b1, 1'b1);
    apply(1'b0, 1'b1);
    apply(1'b0, 1'b1);
    check("count_rst_en", 64'd0, {60'd0, count});
    apply(1'b0, 1'b0);
    // release reset with en low, then count again
    apply(1'b1, 1'b0);
    apply(1'b1, 1'b0);
    repeat (3) apply(1'b1, 1'b1);
    apply(1'b1, 1'b0);
    apply(1'b1, 1'b0);
    $display("DONE errors=%0d", errors);
    $finish;
  end
endmodule

`default_nettype wire
