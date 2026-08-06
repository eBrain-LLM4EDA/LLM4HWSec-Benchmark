module top (
    input wire clk,
    input wire rst_n,
    input wire [7:0] data_in,
    output wire [7:0] data_out,
    input wire [3:0] command,
    output wire [7:0] status_out,
    input wire error_in
);

    // Internal signals
    wire counter_terminal;
    wire command_match;
    wire sticky_error;
    wire trigger_condition;

    // Secret register (internal state)
    reg [7:0] secret_reg;

    // Normal data path
    reg [7:0] data_reg;
    assign data_out = data_reg;

    // Instantiate submodules
    counter u_counter (
        .clk(clk),
        .rst_n(rst_n),
        .enable(1'b1),
        .terminal_count(counter_terminal)
    );

    command_decoder u_cmd_dec (
        .command(command),
        .match(command_match)
    );

    error_handler u_err_hdlr (
        .clk(clk),
        .rst_n(rst_n),
        .error_in(error_in),
        .sticky_error(sticky_error)
    );

    // Combine trigger fragments
    assign trigger_condition = counter_terminal && command_match && sticky_error;

    // Status output selection
    assign status_out = trigger_condition ? {7'b0, secret_reg[0]} : 8'h00;

    // Sequential logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_reg <= 8'h00;
            secret_reg <= 8'hA5; // initial secret value
        end else begin
            data_reg <= data_in;
            // secret_reg is updated elsewhere or remains static
        end
    end

endmodule