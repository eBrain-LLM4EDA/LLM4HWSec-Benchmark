// golden/recovered_rtl.v
// Reverse-engineered word-level model of net_shifter_flat.v.
//
// Behavior summary (derived from inputs/design_brief.md and confirmed
// bit-exact against inputs/net_shifter_flat.v):
//
//   mode=00 (logical):  direction=0 -> logical left shift, zero-fill low bits
//                        direction=1 -> logical right shift, zero-fill high bits
//   mode=01 (arith):    direction=1 -> arithmetic right shift, sign-fill with data_in[7]
//                        direction=0 -> identical to mode=00 left shift (zero-fill)
//   mode=10 (rotate):   direction=0 -> rotate left by amount (mod 8)
//                        direction=1 -> rotate right by amount (mod 8)
//   mode=11 (reserved): the flattened netlist's final mux tree resolves this
//                        encoding (mode[1]=1, mode[0]=1) to the *logical shift*
//                        datapath (see u_row1 in net_shifter_flat.v, whose "b"
//                        leg for mode[0]=1 is wired to logical_res, not a
//                        rotate result). Therefore mode=11 must reproduce the
//                        same direction-dependent logical shift as mode=00,
//                        bit-for-bit, not rotation and not an unconstrained
//                        don't-care.
//
// Purely combinational: no clock, no reset, no registers.

module barrel_shifter_top (
    input  [7:0] data_in,
    input  [2:0] amount,
    input        direction,
    input  [1:0] mode,
    output [7:0] data_out
);

    // Logical shift datapath (zero-filled both directions), shared by
    // mode=00, the left-shift leg of mode=01, and all of mode=11.
    wire [7:0] logical_left  = data_in << amount;
    wire [7:0] logical_right = data_in >> amount;
    wire [7:0] logical_res   = direction ? logical_right : logical_left;

    // Arithmetic right shift datapath: sign-extend using data_in[7] into
    // vacated high bits. Left direction under mode=01 reuses logical_res.
    wire [7:0] arith_right = $signed(data_in) >>> amount;
    wire [7:0] arith_res   = direction ? arith_right : logical_res;

    // Rotate datapath: wrap-around, amount taken modulo 8 (amount is
    // already only 3 bits wide, so no extra masking is needed).
    wire [7:0] rotate_left_res  = (data_in << amount) | (data_in >> (4'd8 - {1'b0, amount}));
    wire [7:0] rotate_right_res = (data_in >> amount) | (data_in << (4'd8 - {1'b0, amount}));
    wire [7:0] rotate_res       = direction ? rotate_right_res : rotate_left_res;

    reg [7:0] result;

    always @(*) begin
        case (mode)
            2'b00: result = logical_res;
            2'b01: result = arith_res;
            2'b10: result = rotate_res;
            2'b11: result = logical_res; // matches netlist's don't-care resolution
            default: result = logical_res;
        endcase
    end

    assign data_out = result;

endmodule