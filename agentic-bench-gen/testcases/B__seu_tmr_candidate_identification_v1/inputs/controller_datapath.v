// controller_datapath.v
//
// Small controller + datapath module: an FSM sequences loading of two
// operands, a multiply-accumulate datapath stage, and writes results into
// a small output FIFO. Provided as a self-contained synthesizable example.

module controller_datapath (
    input  wire        clk,
    input  wire         rst_n,

    input  wire         start,
    input  wire  [15:0] data_in,
    input  wire  [1:0]  mode_in,
    input  wire         mode_wr_en,
    input  wire         irq_ack,
    input  wire         fifo_rd_en,

    output wire  [2:0]  ctrl_state_o,
    output wire  [31:0] result_o,
    output wire         irq_pending_o,
    output wire         fifo_empty_o,
    output wire         fifo_full_o
);

    localparam [2:0] IDLE    = 3'd0,
                      LOAD    = 3'd1,
                      COMPUTE = 3'd2,
                      OUTPUT  = 3'd3,
                      ERROR   = 3'd4;

    reg [2:0]  ctrl_state;
    reg [1:0]  mode_reg;
    reg        irq_pending_reg;
    reg [3:0]  fifo_wr_ptr;
    reg [3:0]  fifo_rd_ptr;
    reg [31:0] mac_acc_reg;
    reg [15:0] data_stage1_reg;
    reg [15:0] data_stage2_reg;

    reg [15:0] fifo_mem [0:15];
    reg [3:0]  load_count;

    wire [31:0] mult_result;
    assign mult_result = data_stage1_reg * data_stage2_reg;

    assign ctrl_state_o   = ctrl_state;
    assign result_o       = mac_acc_reg;
    assign irq_pending_o  = irq_pending_reg;
    assign fifo_empty_o   = (fifo_wr_ptr == fifo_rd_ptr);
    assign fifo_full_o    = ((fifo_wr_ptr + 4'd1) == fifo_rd_ptr);

    // Main controller FSM
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ctrl_state <= IDLE;
            load_count <= 4'd0;
        end else begin
            case (ctrl_state)
                IDLE: begin
                    if (start) begin
                        ctrl_state <= LOAD;
                        load_count <= 4'd0;
                    end
                end

                LOAD: begin
                    if (load_count == 4'd1) begin
                        ctrl_state <= COMPUTE;
                    end else begin
                        load_count <= load_count + 4'd1;
                    end
                end

                COMPUTE: begin
                    ctrl_state <= OUTPUT;
                end

                OUTPUT: begin
                    if (((fifo_wr_ptr + 4'd1)) == fifo_rd_ptr) begin
                        ctrl_state <= ERROR;
                    end else begin
                        ctrl_state <= IDLE;
                    end
                end

                ERROR: begin
                    if (irq_ack) begin
                        ctrl_state <= IDLE;
                    end
                end

                default: begin
                    ctrl_state <= IDLE;
                end
            endcase
        end
    end

    // Mode/config latch: updated on explicit write enable only.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mode_reg <= 2'b00;
        end else if (mode_wr_en) begin
            mode_reg <= mode_in;
        end
    end

    // Interrupt-pending flag: set on entry to ERROR state, cleared on ack.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            irq_pending_reg <= 1'b0;
        end else if (ctrl_state == OUTPUT && ((fifo_wr_ptr + 4'd1) == fifo_rd_ptr)) begin
            irq_pending_reg <= 1'b1;
        end else if (irq_ack) begin
            irq_pending_reg <= 1'b0;
        end
    end

    // Input pipeline staging registers, loaded during LOAD state.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_stage1_reg <= 16'd0;
            data_stage2_reg <= 16'd0;
        end else if (ctrl_state == LOAD) begin
            data_stage1_reg <= data_stage2_reg;
            data_stage2_reg <= data_in;
        end
    end

    // Multiply-accumulate register: sums pipeline product during COMPUTE.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mac_acc_reg <= 32'd0;
        end else if (ctrl_state == COMPUTE) begin
            mac_acc_reg <= mac_acc_reg + mult_result;
        end else if (ctrl_state == IDLE && start) begin
            mac_acc_reg <= 32'd0;
        end
    end

    // Output FIFO write pointer: advances when a result is pushed.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fifo_wr_ptr <= 4'd0;
        end else if (ctrl_state == OUTPUT && ((fifo_wr_ptr + 4'd1) != fifo_rd_ptr)) begin
            fifo_mem[fifo_wr_ptr] <= data_stage2_reg;
            fifo_wr_ptr <= fifo_wr_ptr + 4'd1;
        end
    end

    // Output FIFO read pointer: advances on external read request.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fifo_rd_ptr <= 4'd0;
        end else if (fifo_rd_en && (fifo_wr_ptr != fifo_rd_ptr)) begin
            fifo_rd_ptr <= fifo_rd_ptr + 4'd1;
        end
    end

endmodule