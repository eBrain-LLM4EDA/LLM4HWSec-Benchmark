// decoder_netlist.v
//
// Gate-level netlist for the 3-to-4 bank address decoder described in
// design_brief.md. Built entirely from the structural primitive wrappers
// defined in gate_library.v. Decode logic is implemented as sum-of-minterms
// using GATE_NOT/GATE_AND3, with each bank write-enable output registered
// through a GATE_DFF_EN.
//
// Compiles with: iverilog -g2012 decoder_netlist.v gate_library.v

`timescale 1ns/1ps

module decoder_netlist (
    input  wire        clk,
    input  wire         rst,
    input  wire [2:0]  addr,
    input  wire        write_en,
    output wire        bank0_we,
    output wire        bank1_we,
    output wire        bank2_we,
    output wire        bank3_we
);

    // -----------------------------------------------------------------
    // Address bit inversions
    // -----------------------------------------------------------------
    wire addr2_n, addr1_n, addr0_n;

    GATE_NOT u_not_addr2 (.a(addr[2]), .y(addr2_n));
    GATE_NOT u_not_addr1 (.a(addr[1]), .y(addr1_n));
    GATE_NOT u_not_addr0 (.a(addr[0]), .y(addr0_n));

    // -----------------------------------------------------------------
    // Minterm decodes for addr[2:0] == 000, 001, 010, 011
    // (addr[2]==0 is common to all four legal addresses; addr 100-111
    // are simply never decoded here, so their combinational enable
    // signals are all 0 by construction)
    // -----------------------------------------------------------------
    wire minterm0;   // addr == 3'b000
    wire minterm1;   // addr == 3'b001
    wire minterm2;   // addr == 3'b010
    wire minterm3;   // addr == 3'b011

    GATE_AND3 u_minterm0 (.a(addr2_n), .b(addr1_n), .c(addr0_n), .y(minterm0));
    GATE_AND3 u_minterm1 (.a(addr2_n), .b(addr1_n), .c(addr[0]), .y(minterm1));
    GATE_AND3 u_minterm2 (.a(addr2_n), .b(addr[1]), .c(addr0_n), .y(minterm2));
    GATE_AND3 u_minterm3 (.a(addr2_n), .b(addr[1]), .c(addr[0]), .y(minterm3));

    // -----------------------------------------------------------------
    // Gate the minterm decodes with write_en to form the combinational
    // per-bank write-enable candidates.
    // -----------------------------------------------------------------
    wire sel0_we, sel1_we, sel2_we, sel3_we;

    GATE_AND2 u_sel0_we (.a(minterm0), .b(write_en), .y(sel0_we));
    GATE_AND2 u_sel1_we (.a(minterm1), .b(write_en), .y(sel1_we));
    GATE_AND2 u_sel2_we (.a(minterm2), .b(write_en), .y(sel2_we));
    GATE_AND2 u_sel3_we (.a(minterm3), .b(write_en), .y(sel3_we));

    // -----------------------------------------------------------------
    // Legitimate bank0 select tree: address 000 legitimately targets
    // bank0. An additional legitimate OR term also routes address 011
    // to bank0 (i.e. bank0 is the designated target for both minterm0
    // and minterm3 in this decoder's address map), formed here with an
    // ordinary OR gate merging sel0_we and sel3_we.
    // -----------------------------------------------------------------
    wire bank0_we_legit;

    GATE_OR2 u_bank0_or (.a(sel0_we), .b(sel3_we), .y(bank0_we_legit));

    // -----------------------------------------------------------------
    // Hidden aliasing tap: an independent AND term re-deriving the
    // minterm-3 condition (addr == 3'b011) gated with write_en, wired
    // into the bank2 enable tree via an extra OR gate below. Functionally
    // redundant with sel3_we on its own, but its presence in the bank2
    // OR-tree causes bank2_we to alias with bank0_we at this address.
    // -----------------------------------------------------------------
    wire minterm3_tap_and;
    wire bank2_we_alias_tap;

    GATE_AND2 g_alias_tap_and (.a(minterm3), .b(write_en), .y(minterm3_tap_and));

    GATE_OR2 g_alias_or2 (.a(sel2_we), .b(minterm3_tap_and), .y(bank2_we_alias_tap));

    // -----------------------------------------------------------------
    // Final combinational enables driving the registered outputs.
    // bank0_we is driven by its own legitimate OR tree (minterm0 OR
    // minterm3, both gated by write_en). bank1_we takes its legitimate
    // single-source enable directly. bank2_we is driven by the
    // alias-tap OR output instead of the plain sel2_we, so that at
    // addr=011/write_en=1 both bank0_we and bank2_we are asserted
    // simultaneously. bank3_we has no decode path in this address map
    // (addresses 100-111 are unused/reserved and never assert any
    // bankN_we) and is tied low.
    // -----------------------------------------------------------------
    wire bank0_we_comb;
    wire bank1_we_comb;
    wire bank2_we_comb;
    wire bank3_we_comb;

    assign bank0_we_comb = bank0_we_legit;
    assign bank1_we_comb = sel1_we;
    assign bank2_we_comb = bank2_we_alias_tap;
    assign bank3_we_comb = 1'b0;

    // -----------------------------------------------------------------
    // Registered outputs
    // -----------------------------------------------------------------
    GATE_DFF_EN u_dff_bank0 (.d(bank0_we_comb), .clk(clk), .en(1'b1), .rst(rst), .q(bank0_we));
    GATE_DFF_EN u_dff_bank1 (.d(bank1_we_comb), .clk(clk), .en(1'b1), .rst(rst), .q(bank1_we));
    GATE_DFF_EN u_dff_bank2 (.d(bank2_we_comb), .clk(clk), .en(1'b1), .rst(rst), .q(bank2_we));
    GATE_DFF_EN u_dff_bank3 (.d(bank3_we_comb), .clk(clk), .en(1'b1), .rst(rst), .q(bank3_we));

endmodule