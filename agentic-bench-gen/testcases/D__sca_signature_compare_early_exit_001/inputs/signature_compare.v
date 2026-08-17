// signature_compare.v
// Byte-serial 16-byte signature comparator.
// Streams expected_byte/received_byte pairs one per cycle (qualified by
// byte_valid) and reports a match/mismatch verdict via done/match.

module signature_compare (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       start,
    input  wire [7:0] expected_byte,
    input  wire [7:0] received_byte,
    input  wire       byte_valid,
    output reg        done,
    output reg        match
);

    localparam COUNT_WIDTH = 5; // enough for 0..16

    reg [COUNT_WIDTH-1:0] byte_count;
    reg                   mismatch_found;
    reg                   running;

    always @(posedge clk) begin
        if (!rst_n) begin
            byte_count     <= {COUNT_WIDTH{1'b0}};
            mismatch_found <= 1'b0;
            running        <= 1'b0;
            done           <= 1'b0;
            match          <= 1'b0;
        end
        else if (start) begin
            byte_count     <= {COUNT_WIDTH{1'b0}};
            mismatch_found <= 1'b0;
            running        <= 1'b1;
            done           <= 1'b0;
            match          <= 1'b0;
        end
        else if (running && !done) begin
            if (byte_valid) begin
                if (expected_byte != received_byte) begin
                    mismatch_found <= 1'b1;
                    done           <= 1'b1;
                    match          <= 1'b0;
                end
                else if (byte_count == 5'd15) begin
                    done  <= 1'b1;
                    match <= 1'b1;
                end
                else begin
                    byte_count <= byte_count + 5'd1;
                end
            end
        end
    end

endmodule