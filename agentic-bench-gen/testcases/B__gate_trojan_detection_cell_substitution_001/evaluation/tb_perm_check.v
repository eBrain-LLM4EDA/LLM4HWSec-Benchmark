`timescale 1ns/1ps

//
// tb_perm_check.v
//
// Exhaustive testbench for the perm_check module. Instantiates the
// design purely via its pinned public interface (module name
// perm_check, ports id_in/id_auth/grant) with no dependency on any
// internal net or instance names, and sweeps all 16x16 = 256
// combinations of id_in and id_auth, printing one machine-readable
// RESULT line per combination.
//
// Must be co-compiled with inputs/primitive_cells.v and
// inputs/netlist.v, e.g.:
//   iverilog -g2012 -o sim.vvp inputs/primitive_cells.v inputs/netlist.v evaluation/tb_perm_check.v
//   vvp sim.vvp
//

module tb_perm_check;

    reg  [3:0] id_in;
    reg  [3:0] id_auth;
    wire       grant;

    integer i, j;

    perm_check dut (
        .id_in   (id_in),
        .id_auth (id_auth),
        .grant   (grant)
    );

    initial begin
        for (j = 0; j < 16; j = j + 1) begin
            id_auth = j[3:0];
            for (i = 0; i < 16; i = i + 1) begin
                id_in = i[3:0];
                #1;
                $display("RESULT %b %b %b",
                          {id_in[3], id_in[2], id_in[1], id_in[0]},
                          {id_auth[3], id_auth[2], id_auth[1], id_auth[0]},
                          grant);
            end
        end
        $finish;
    end

endmodule