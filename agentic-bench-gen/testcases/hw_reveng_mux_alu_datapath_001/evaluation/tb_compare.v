// tb_compare.v
//
// Self-contained comparison testbench: drives the submission's
// `recovered_datapath` (submission/recovered_rtl.v) with a deterministic
// stimulus set (no $random, no wall-clock dependence) and computes the
// expected reference value directly, behaviorally, per the public spec's
// literal FR2-FR4 definitions:
//   sel=00 -> a+b (8-bit wraparound)
//   sel=01 -> a-b (8-bit two's-complement wraparound)
//   sel=10 -> a & b
//   sel=11 -> a | b
//
// This testbench deliberately does NOT instantiate inputs/gate_netlist.v.
// That reference file's internal ripple-carry chain contains a
// self-referencing multiply-driven net pattern that produces X on its y
// output for essentially all sel=00/01 vectors under real iverilog
// simulation, making direct signal comparison against it unusable even
// for a genuinely correct recovered module. Instead, the expected value
// is computed here with ordinary behavioral Verilog arithmetic (8-bit
// reg operands truncate naturally to give modulo-256 wraparound),
// independent of any baseline styling or gate-level artifact.
//
// This file is NOT part of inputs/ -- it is shipped by the evaluator and
// compiled alongside the submission only.

`timescale 1ns/1ps

module tb_compare;

    reg  [7:0] a;
    reg  [7:0] b;
    reg  [1:0] sel;

    wire [7:0] rec_y;

    // Submission under test, connected via explicit named ports so any
    // port name/width mismatch relative to the pinned interface is an
    // elaboration error (caught as an FR1 compile failure).
    recovered_datapath rec_dut (
        .a   (a),
        .b   (b),
        .sel (sel),
        .y   (rec_y)
    );

    // Evaluator-authored behavioral reference, independent of any
    // gate-level or baseline-styled implementation.
    reg [7:0] expected_y;

    always @(*) begin
        case (sel)
            2'b00: expected_y = a + b;
            2'b01: expected_y = a - b;
            2'b10: expected_y = a & b;
            2'b11: expected_y = a | b;
            default: expected_y = 8'bx;
        endcase
    end

    integer sel_idx;
    integer pair_idx;
    integer rnd_idx;

    // Fixed directed (a,b) pairs applied for every sel value.
    reg [7:0] directed_a [0:9];
    reg [7:0] directed_b [0:9];

    // Deterministic pseudo-random sweep state (simple LCG, fixed seed --
    // NOT $random, fully reproducible across runs/tools).
    reg [31:0] lcg_state;

    task lcg_step;
        begin
            // Classic LCG constants (Numerical Recipes). Deterministic,
            // no dependence on simulator RNG or wall clock.
            lcg_state = (lcg_state * 32'd1664525) + 32'd1013904223;
        end
    endtask

    task apply_and_print;
        begin
            #1;
            $display("VEC sel=%0d a=%0d b=%0d rec=%0d exp=%0d match=%0d",
                      sel, a, b, rec_y, expected_y,
                      (rec_y === expected_y) ? 1 : 0);
        end
    endtask

    initial begin
        // Initialize directed vector table.
        directed_a[0] = 8'd0;   directed_b[0] = 8'd0;
        directed_a[1] = 8'd255; directed_b[1] = 8'd255;
        directed_a[2] = 8'd255; directed_b[2] = 8'd1;
        directed_a[3] = 8'd1;   directed_b[3] = 8'd255;
        directed_a[4] = 8'd0;   directed_b[4] = 8'd1;
        directed_a[5] = 8'd1;   directed_b[5] = 8'd0;
        directed_a[6] = 8'd5;   directed_b[6] = 8'd3;
        directed_a[7] = 8'd3;   directed_b[7] = 8'd5;
        directed_a[8] = 8'd128; directed_b[8] = 8'd128;
        directed_a[9] = 8'd127; directed_b[9] = 8'd128;

        for (sel_idx = 0; sel_idx < 4; sel_idx = sel_idx + 1) begin
            sel = sel_idx[1:0];

            // Fixed seed per sel value so the full sweep is fully
            // deterministic and reproducible run to run.
            lcg_state = 32'h2545F491 + (sel_idx * 32'h9E3779B9);

            // Directed vectors.
            for (pair_idx = 0; pair_idx < 10; pair_idx = pair_idx + 1) begin
                a = directed_a[pair_idx];
                b = directed_b[pair_idx];
                apply_and_print;
            end

            // Deterministic pseudo-random sweep (50 pairs per sel).
            for (rnd_idx = 0; rnd_idx < 50; rnd_idx = rnd_idx + 1) begin
                lcg_step;
                a = lcg_state[15:8];
                lcg_step;
                b = lcg_state[23:16];
                apply_and_print;
            end
        end

        $finish;
    end

endmodule