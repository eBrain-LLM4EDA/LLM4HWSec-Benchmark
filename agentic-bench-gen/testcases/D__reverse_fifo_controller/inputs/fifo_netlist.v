// Flattened gate-level netlist for a 4-entry, 8-bit synchronous FIFO
// Module: fifo_controller
// This netlist uses only DFFs, multiplexers, and basic gates.
// No hierarchy; all logic is flattened.

module fifo_controller (
    input         clk,
    input         rst,
    input  [7:0]  write_data,
    input         write_en,
    input         read_en,
    output [7:0]  read_data,
    output        full,
    output        empty
);

    // Internal wires for pointer and counter logic
    wire [1:0] wptr_next, rptr_next;
    wire [2:0] occ_next;
    wire [1:0] wptr, rptr;
    wire [2:0] occ;
    wire [7:0] mem0, mem1, mem2, mem3;
    wire [7:0] mem0_next, mem1_next, mem2_next, mem3_next;
    wire [7:0] read_data_next;
    wire write_ok, read_ok;
    wire full_int, empty_int;
    wire [1:0] wptr_inc, rptr_inc;
    wire [2:0] occ_inc, occ_dec, occ_same;
    wire [7:0] read_mux_out;

    // Write and read enable qualification
    assign write_ok = write_en & ~full_int;
    assign read_ok  = read_en & ~empty_int;

    // Pointer increment logic
    assign wptr_inc = wptr + 2'd1;
    assign rptr_inc = rptr + 2'd1;

    // Next pointer values
    assign wptr_next = write_ok ? wptr_inc : wptr;
    assign rptr_next = read_ok  ? rptr_inc : rptr;

    // Occupancy counter logic
    assign occ_inc  = occ + 3'd1;
    assign occ_dec  = occ - 3'd1;
    assign occ_same = occ;

    assign occ_next = (write_ok & ~read_ok)  ? occ_inc :
                      (~write_ok & read_ok)  ? occ_dec :
                      occ_same;

    // Full and empty flags (combinational from occupancy)
    assign full_int  = (occ == 3'd4);
    assign empty_int = (occ == 3'd0);

    // Memory write enables (one-hot decoded from wptr)
    wire w0, w1, w2, w3;
    assign w0 = write_ok & (wptr == 2'd0);
    assign w1 = write_ok & (wptr == 2'd1);
    assign w2 = write_ok & (wptr == 2'd2);
    assign w3 = write_ok & (wptr == 2'd3);

    // Memory next values (mux between write_data and current content)
    assign mem0_next = w0 ? write_data : mem0;
    assign mem1_next = w1 ? write_data : mem1;
    assign mem2_next = w2 ? write_data : mem2;
    assign mem3_next = w3 ? write_data : mem3;

    // Read data mux (combinational from rptr)
    assign read_mux_out = (rptr == 2'd0) ? mem0 :
                          (rptr == 2'd1) ? mem1 :
                          (rptr == 2'd2) ? mem2 :
                          mem3;

    // Registered read data output
    assign read_data_next = read_mux_out;

    // DFF instances for pointers, occupancy, memory, and read_data
    // All with synchronous active-high reset

    // Write pointer DFFs
    dff_sync_reset #(2) wptr_reg (
        .clk(clk),
        .rst(rst),
        .d(wptr_next),
        .q(wptr)
    );

    // Read pointer DFFs
    dff_sync_reset #(2) rptr_reg (
        .clk(clk),
        .rst(rst),
        .d(rptr_next),
        .q(rptr)
    );

    // Occupancy counter DFFs
    dff_sync_reset #(3) occ_reg (
        .clk(clk),
        .rst(rst),
        .d(occ_next),
        .q(occ)
    );

    // Memory DFFs (8-bit each)
    dff_sync_reset #(8) mem0_reg (
        .clk(clk),
        .rst(rst),
        .d(mem0_next),
        .q(mem0)
    );

    dff_sync_reset #(8) mem1_reg (
        .clk(clk),
        .rst(rst),
        .d(mem1_next),
        .q(mem1)
    );

    dff_sync_reset #(8) mem2_reg (
        .clk(clk),
        .rst(rst),
        .d(mem2_next),
        .q(mem2)
    );

    dff_sync_reset #(8) mem3_reg (
        .clk(clk),
        .rst(rst),
        .d(mem3_next),
        .q(mem3)
    );

    // Read data output DFF
    dff_sync_reset #(8) rd_reg (
        .clk(clk),
        .rst(rst),
        .d(read_data_next),
        .q(read_data)
    );

    // Output full and empty (registered to match Moore timing)
    dff_sync_reset #(1) full_reg (
        .clk(clk),
        .rst(rst),
        .d(full_int),
        .q(full)
    );

    dff_sync_reset #(1) empty_reg (
        .clk(clk),
        .rst(rst),
        .d(empty_int),
        .q(empty)
    );

endmodule

// Generic DFF with synchronous active-high reset
module dff_sync_reset #(
    parameter WIDTH = 1
) (
    input              clk,
    input              rst,
    input  [WIDTH-1:0] d,
    output [WIDTH-1:0] q
);
    reg [WIDTH-1:0] q_reg;
    always @(posedge clk) begin
        if (rst)
            q_reg <= {WIDTH{1'b0}};
        else
            q_reg <= d;
    end
    assign q = q_reg;
endmodule