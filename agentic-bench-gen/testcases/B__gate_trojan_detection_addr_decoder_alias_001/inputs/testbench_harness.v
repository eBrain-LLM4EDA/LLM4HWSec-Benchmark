// testbench_harness.v
//
// Exhaustive testbench for decoder_netlist. Drives all 8 values of
// addr[2:0] crossed with both values of write_en (16 total vectors),
// applying each combination for one full clock cycle and reporting the
// resulting registered bank0_we..bank3_we outputs via $display. This
// testbench makes no hardcoded pass/fail assertions against a golden
// table; it simply exposes the decoder's observed behavior so that it
// can be inspected (manually or by an external checker) for compliance
// with the one-hot decode invariant described in design_brief.md.
//
// Compiles and runs with:
//   iverilog -g2012 -o sim testbench_harness.v decoder_netlist.v gate_library.v
//   vvp sim

`timescale 1ns/1ps

module tb_decoder_netlist;

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

    // -----------------------------------------------------------------
    // Device under test
    // -----------------------------------------------------------------
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

    // -----------------------------------------------------------------
    // Clock generation: 10ns period
    // -----------------------------------------------------------------
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // -----------------------------------------------------------------
    // Stimulus and reporting
    // -----------------------------------------------------------------
    initial begin
        rst      = 1'b1;
        addr     = 3'b000;
        write_en = 1'b0;

        // Hold reset across a couple of rising edges to clear all
        // registered write-enables.
        @(posedge clk);
        @(posedge clk);
        rst = 1'b0;

        $display("addr write_en bank0_we bank1_we bank2_we bank3_we");

        for (addr_val = 0; addr_val < 8; addr_val = addr_val + 1) begin
            for (we_val = 0; we_val < 2; we_val = we_val + 1) begin
                addr     = addr_val[2:0];
                write_en = we_val[0];

                // Allow combinational decode to settle, then capture the
                // registered outputs on the next rising edge.
                @(posedge clk);
                #1;

                $display("%b     %b        %b        %b        %b        %b",
                          addr, write_en, bank0_we, bank1_we, bank2_we, bank3_we);
            end
        end

        $finish;
    end

endmodule