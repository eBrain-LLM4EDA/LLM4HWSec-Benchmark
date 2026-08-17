// tb_perm_cone.v
// Exhaustive testbench for perm_cone: enumerates all 32 combinations of
// req_level[1:0] and owner_id[2:0], applies each vector, and prints a
// single machine-parseable line per vector for cross-checking against
// the Python gate-level simulator used in evaluate.py.
//
// Output line format (exact, %b padded to width via reg width):
//   VEC req_level=<2 bits> owner_id=<3 bits> grant=<1 bit>

`timescale 1ns/1ps

module tb_perm_cone;

  reg  [1:0] req_level;
  reg  [2:0] owner_id;
  wire       grant;

  integer i, j;

  perm_cone dut (
      .req_level(req_level),
      .owner_id(owner_id),
      .grant(grant)
  );

  initial begin
    for (i = 0; i < 4; i = i + 1) begin
      for (j = 0; j < 8; j = j + 1) begin
        req_level = i[1:0];
        owner_id  = j[2:0];
        #1;
        $display("VEC req_level=%b owner_id=%b grant=%b", req_level, owner_id, grant);
      end
    end
    $finish;
  end

endmodule