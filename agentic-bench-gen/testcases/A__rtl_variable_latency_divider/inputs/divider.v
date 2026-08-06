// divider.v
// Iterative unsigned divider with early termination

module divider #(
    parameter WIDTH = 8
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 start,
    input  wire [WIDTH-1:0]     dividend,
    input  wire [WIDTH-1:0]     divisor,
    output reg                  done,
    output reg  [WIDTH-1:0]     quotient,
    output reg  [WIDTH-1:0]     remainder
);

    // Internal state
    reg [WIDTH-1:0]             a_reg;      // remainder accumulator
    reg [WIDTH-1:0]             q_reg;      // quotient accumulator
    reg [WIDTH-1:0]             b_reg;      // divisor
    reg [$clog2(WIDTH):0]       count;      // iteration counter
    reg                         busy;

    // Early termination signal
    wire                        early_done;

    assign early_done = (a_reg == {WIDTH{1'b0}}) && busy;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a_reg      <= {WIDTH{1'b0}};
            q_reg      <= {WIDTH{1'b0}};
            b_reg      <= {WIDTH{1'b0}};
            count      <= 0;
            busy       <= 1'b0;
            done       <= 1'b0;
            quotient   <= {WIDTH{1'b0}};
            remainder  <= {WIDTH{1'b0}};
        end else begin
            if (start && !busy) begin
                // Load operands and initialize
                a_reg      <= dividend;
                q_reg      <= {WIDTH{1'b0}};
                b_reg      <= divisor;
                count      <= WIDTH;
                busy       <= 1'b1;
                done       <= 1'b0;
            end else if (busy) begin
                if (early_done) begin
                    // Early termination: remaining dividend is zero
                    done       <= 1'b1;
                    quotient   <= q_reg;
                    remainder  <= a_reg;
                    busy       <= 1'b0;
                end else if (count == 0) begin
                    // Normal completion after WIDTH iterations
                    done       <= 1'b1;
                    quotient   <= q_reg;
                    remainder  <= a_reg;
                    busy       <= 1'b0;
                end else begin
                    // Shift-subtract iteration
                    a_reg <= {a_reg[WIDTH-2:0], 1'b0};
                    if (a_reg[WIDTH-1] || (a_reg >= b_reg)) begin
                        a_reg <= a_reg - b_reg;
                        q_reg <= {q_reg[WIDTH-2:0], 1'b1};
                    end else begin
                        q_reg <= {q_reg[WIDTH-2:0], 1'b0};
                    end
                    count <= count - 1;
                end
            end else begin
                done <= 1'b0;
            end
        end
    end

endmodule