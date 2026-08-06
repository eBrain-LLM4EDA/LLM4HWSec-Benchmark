// timeout_module.v
// Dual-counter timeout module with shared enable generation.
// Two independent counters must agree; timeout asserts after a configured number of cycles.

module timeout_module (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       start,
    output reg        timeout,
    output reg        error
);

    // Parameters
    parameter TIMEOUT_CYCLES = 16'd1000;  // Timeout threshold

    // Internal signals
    wire        shared_count_en;
    wire [15:0] count_a;
    wire [15:0] count_b;
    wire        counters_equal;
    wire        threshold_reached;

    // Enable generation logic (shared cone)
    // The enable is active when start is high and we haven't timed out yet.
    assign shared_count_en = start && !timeout;

    // Counter A instance
    counter #(
        .WIDTH(16)
    ) counter_a (
        .clk    (clk),
        .rst_n  (rst_n),
        .en     (shared_count_en),
        .count  (count_a)
    );

    // Counter B instance
    counter #(
        .WIDTH(16)
    ) counter_b (
        .clk    (clk),
        .rst_n  (rst_n),
        .en     (shared_count_en),
        .count  (count_b)
    );

    // Equality comparator
    assign counters_equal = (count_a == count_b);

    // Timeout threshold detection
    assign threshold_reached = (count_a >= TIMEOUT_CYCLES) && (count_b >= TIMEOUT_CYCLES);

    // Sequential logic for timeout and error outputs
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            timeout <= 1'b0;
            error   <= 1'b0;
        end else begin
            // Timeout asserts when threshold is reached and counters are equal
            if (threshold_reached && counters_equal) begin
                timeout <= 1'b1;
            end
            // Error asserts if counters ever disagree
            if (!counters_equal) begin
                error <= 1'b1;
            end
        end
    end

endmodule


// Simple parameterizable counter module
module counter #(
    parameter WIDTH = 16
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             en,
    output reg  [WIDTH-1:0] count
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= {WIDTH{1'b0}};
        end else if (en) begin
            count <= count + 1'b1;
        end
    end

endmodule