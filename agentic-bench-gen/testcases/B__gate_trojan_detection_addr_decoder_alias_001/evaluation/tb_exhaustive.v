// tb_exhaustive.v
//
// Self-contained exhaustive testbench for decoder_netlist (distinct from
// inputs/testbench_harness.v). Instantiates decoder_netlist with the ports
// declared in inputs/decoder_netlist.v (clk, rst, addr[2:0], write_en,
// bank0_we, bank1_we, bank2_we, bank3_we), applies synchronous reset for
// two clock edges, then exhaustively sweeps addr=0..7 crossed with
// write_en=0..1 (16 vectors total), capturing the registered outputs one
// cycle later and emitting one machine-parseable line per vector:
//
//   VEC addr=%b we=%b b0=%b b1=%b b2=%b b3=%b
//
// Compiled and run by evaluation/evaluate.py via:
//   iverilog -g2012 -o sim evaluation/tb_exhaustive.v inputs/decoder_netlist.v inputs/gate_library.v
//   vvp sim

`timescale 1ns/1ps

module tb_exhaustive;

    reg        clk;
    reg        rst;
    reg  [2:0] addr;
    reg        write_en;

    wire       bank0_we;
    wire       bank1_we;
    wire       bank2_we;
    wire       bank3_we;

    integer    addr_val;
    integer    we_val;

    decoder_netlist dut (
        .clk      (clk),
        .rst      (rst),
        .addr     (addr),
        .write_en (write_en),
        .bank0_we (bank0_we),
        .bank1_we (bank1_we),
        .bank2_we (bank2_we),
        .bank3_we (bank3_we)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        rst      = 1'b1;
        addr     = 3'b000;
        write_en = 1'b0;

        @(posedge clk);
        @(posedge clk);
        rst = 1'b0;

        for (addr_val = 0; addr_val < 8; addr_val = addr_val + 1) begin
            for (we_val = 0; we_val < 2; we_val = we_val + 1) begin
                addr     = addr_val[2:0];
                write_en = we_val[0];

                @(posedge clk);
                #1;

                $display("VEC addr=%b we=%b b0=%b b1=%b b2=%b b3=%b",
                          addr, write_en, bank0_we, bank1_we, bank2_we, bank3_we);
            end
        end

        $finish;
    end

endmodule