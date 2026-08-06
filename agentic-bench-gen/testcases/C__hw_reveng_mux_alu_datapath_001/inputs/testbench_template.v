// Illustrative, standalone self-test testbench for exploring the behavior
// of inputs/gate_netlist.v.
//
// This is NOT the official grading harness -- the real evaluator builds
// its own private testbench and comparison logic against your submission.
// Use this file as a convenient starting point to poke at gate_netlist and
// build your own hypothesis about its word-level behavior before you
// write submission/recovered_rtl.v.
//
// Example usage:
//   iverilog -g2012 -o sim.out inputs/gate_netlist.v inputs/testbench_template.v
//   vvp sim.out

`timescale 1ns/1ps

module testbench_template;

    reg  [7:0] a;
    reg  [7:0] b;
    reg  [1:0] sel;
    wire [7:0] y;

    // Instantiate the reference gate-level netlist under test.
    gate_netlist dut (
        .a   (a),
        .b   (b),
        .sel (sel),
        .y   (y)
    );

    integer i;

    initial begin
        $display("      a        b     sel        y");
        $display("----------------------------------------");

        // A handful of directed stimulus points that are useful when
        // forming a hypothesis: zero, max value, a couple of arbitrary
        // values, and a non-commutative pair (a != b) for every sel.
        a = 8'd0;   b = 8'd0;   sel = 2'b00; #1; print_row;
        a = 8'd0;   b = 8'd0;   sel = 2'b01; #1; print_row;
        a = 8'd0;   b = 8'd0;   sel = 2'b10; #1; print_row;
        a = 8'd0;   b = 8'd0;   sel = 2'b11; #1; print_row;

        a = 8'd255; b = 8'd1;   sel = 2'b00; #1; print_row;
        a = 8'd255; b = 8'd1;   sel = 2'b01; #1; print_row;
        a = 8'd255; b = 8'd1;   sel = 2'b10; #1; print_row;
        a = 8'd255; b = 8'd1;   sel = 2'b11; #1; print_row;

        a = 8'd5;   b = 8'd3;   sel = 2'b00; #1; print_row;
        a = 8'd5;   b = 8'd3;   sel = 2'b01; #1; print_row;
        a = 8'd3;   b = 8'd5;   sel = 2'b00; #1; print_row;
        a = 8'd3;   b = 8'd5;   sel = 2'b01; #1; print_row;

        a = 8'hAA;  b = 8'h55;  sel = 2'b10; #1; print_row;
        a = 8'hAA;  b = 8'h55;  sel = 2'b11; #1; print_row;

        // Simple pseudo-random sweep. Feel free to change the seed,
        // vector count, or add your own targeted vectors while exploring
        // locally.
        for (i = 0; i < 20; i = i + 1) begin
            a   = $random;
            b   = $random;
            sel = $random;
            #1;
            print_row;
        end

        $display("Done. Adapt this file freely for local exploration.");
        $finish;
    end

    task print_row;
        begin
            $display("a=%3d (0x%02h)  b=%3d (0x%02h)  sel=%b  ->  y=%3d (0x%02h)",
                      a, a, b, b, sel, y, y);
        end
    endtask

endmodule