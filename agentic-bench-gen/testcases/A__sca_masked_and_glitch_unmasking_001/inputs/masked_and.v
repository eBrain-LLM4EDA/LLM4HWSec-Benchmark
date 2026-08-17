// masked_and.v
//
// Combines two Boolean-shared 1-bit operands (a0,a1) and (b0,b1)
// into a Boolean-shared 1-bit output (q0,q1) such that:
//
//   q0 ^ q1 == (a0 ^ a1) & (b0 ^ b1)
//
// A fresh random bit `r` is used to re-mask the result.

module masked_and (
    input  wire a0,
    input  wire a1,
    input  wire b0,
    input  wire b1,
    input  wire r,
    output wire q0,
    output wire q1
);

    // Partial products between shares of the two operands.
    wire and_same0;   // a0 & b0
    wire and_same1;   // a1 & b1
    wire and_cross0;  // a0 & b1
    wire and_cross1;  // a1 & b0

    assign and_same0  = a0 & b0;
    assign and_same1  = a1 & b1;
    assign and_cross0 = a0 & b1;
    assign and_cross1 = a1 & b0;

    // Combine partial products with the mask to form the output shares.
    assign q0 = and_same0 ^ r;
    assign q1 = and_same1 ^ and_cross0 ^ and_cross1 ^ r;

endmodule