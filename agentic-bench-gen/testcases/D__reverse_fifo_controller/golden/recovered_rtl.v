module fifo_controller (
    input  wire        clk,
    input  wire        rst,
    input  wire [7:0]  write_data,
    input  wire        write_en,
    input  wire        read_en,
    output reg  [7:0]  read_data,
    output wire        full,
    output wire        empty
);

    // Internal state
    reg [1:0] write_ptr;   // 2-bit write pointer (0-3)
    reg [1:0] read_ptr;    // 2-bit read pointer (0-3)
    reg [2:0] occupancy;   // 3-bit occupancy counter (0-4)

    // RAM array: 4 entries of 8 bits each
    reg [7:0] ram [0:3];

    // Full and empty flags (combinational)
    assign full  = (occupancy == 3'd4);
    assign empty = (occupancy == 3'd0);

    // Sequential logic
    always @(posedge clk) begin
        if (rst) begin
            // Synchronous reset: clear all state
            write_ptr <= 2'd0;
            read_ptr  <= 2'd0;
            occupancy <= 3'd0;
            read_data <= 8'd0;
        end else begin
            // Determine if we can write and read this cycle
            // Write allowed if write_en and not full
            // Read allowed if read_en and not empty
            // Simultaneous read/write when neither full nor empty: both proceed

            // Write operation
            if (write_en && !full) begin
                ram[write_ptr] <= write_data;
                write_ptr <= write_ptr + 2'd1;
                // occupancy will be updated below
            end

            // Read operation
            if (read_en && !empty) begin
                // read_data gets the value at current read_ptr (before increment)
                read_data <= ram[read_ptr];
                read_ptr <= read_ptr + 2'd1;
                // occupancy will be updated below
            end else if (!(read_en && !empty)) begin
                // If no read, read_data holds its previous value (already registered)
                // No explicit assignment needed; it retains its value
            end

            // Update occupancy based on write and read enables
            // Note: simultaneous write and read when neither full nor empty -> occupancy unchanged
            if (write_en && !full && !(read_en && !empty)) begin
                // Only write
                occupancy <= occupancy + 3'd1;
            end else if (!(write_en && !full) && read_en && !empty) begin
                // Only read
                occupancy <= occupancy - 3'd1;
            end else if (write_en && !full && read_en && !empty) begin
                // Both write and read: occupancy unchanged
                // No change to occupancy
            end
            // else: neither write nor read, occupancy unchanged
        end
    end

endmodule