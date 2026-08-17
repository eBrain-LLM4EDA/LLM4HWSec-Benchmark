// evaluation/tb_masked_and.v
//
// Testbench used only for the optional FR3 algebraic cross-check in
// evaluation/evaluate.py. It instantiates the masked_and module using
// the pinned port list (a0,a1,b0,b1,r,q0,q1) and drives it with a fixed
// set of stimulus vectors matching the rows found in
// inputs/sim_trace.vcd.txt. For each vector it prints a line of the
// form:
//
//   VEC <idx> <a0><a1><b0><b1><r> <q0><q1>
//
// which evaluate.py parses to cross-check the algebraic invariant
// q0^q1 == (a0^a1)&(b0^b1) independently of the submitted report.

`timescale 1ns/1ps

module tb_masked_and;

    reg a0, a1, b0, b1, r;
    wire q0, q1;

    integer i;

    // Stimulus vectors: a0 a1 b0 b1 r
    // (matches the rows in inputs/sim_trace.vcd.txt)
    reg [4:0] vectors [0:11];

    masked_and dut (
        .a0(a0),
        .a1(a1),
        .b0(b0),
        .b1(b1),
        .r(r),
        .q0(q0),
        .q1(q1)
    );

    initial begin
        // Each entry packs {a0,a1,b0,b1,r}
        vectors[0]  = 5'b00000;
        vectors[1]  = 5'b00001;
        vectors[2]  = 5'b10000;
        vectors[3]  = 5'b01001;
        vectors[4]  = 5'b00100;
        vectors[5]  = 5'b00011;
        vectors[6]  = 5'b11000;
        vectors[7]  = 5'b00111;
        vectors[8]  = 5'b10100;
        vectors[9]  = 5'b01011;
        vectors[10] = 5'b11110;
        vectors[11] = 5'b10011;

        for (i = 0; i < 12; i = i + 1) begin
            a0 = vectors[i][4];
            a1 = vectors[i][3];
            b0 = vectors[i][2];
            b1 = vectors[i][1];
            r  = vectors[i][0];
            #10;
            $display("VEC %0d %b%b%b%b%b %b%b", i, a0, a1, b0, b1, r, q0, q1);
        end

        $finish;
    end

endmodule