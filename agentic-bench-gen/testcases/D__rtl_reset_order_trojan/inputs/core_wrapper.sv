// core_wrapper.sv
// Simple register file + ALU with two reset domains

module core_wrapper (
    input  logic        clk,
    input  logic        core_rst_n,
    input  logic        peri_rst_n,
    input  logic [3:0]  addr,
    input  logic [7:0]  wdata,
    input  logic        we,
    input  logic [1:0]  alu_op,
    output logic [7:0]  rdata,
    output logic        protected_mode
);

    // Register file: 16 x 8-bit
    logic [7:0] regfile [0:15];
    logic [7:0] alu_a, alu_b, alu_result;

    // Internal reset synchronizers and edge detectors
    logic core_rst_sync, peri_rst_sync;
    logic core_rst_prev, peri_rst_prev;
    logic core_release, peri_release;

    // Sticky trigger state
    logic trigger_set;
    logic [1:0] release_counter;

    // Synchronize resets (simple two-stage)
    always_ff @(posedge clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            core_rst_sync <= 1'b0;
            core_rst_prev <= 1'b0;
        end else begin
            core_rst_sync <= 1'b1;
            core_rst_prev <= core_rst_sync;
        end
    end

    always_ff @(posedge clk or negedge peri_rst_n) begin
        if (!peri_rst_n) begin
            peri_rst_sync <= 1'b0;
            peri_rst_prev <= 1'b0;
        end else begin
            peri_rst_sync <= 1'b1;
            peri_rst_prev <= peri_rst_sync;
        end
    end

    // Detect rising edges (reset release)
    assign core_release = core_rst_sync && !core_rst_prev;
    assign peri_release = peri_rst_sync && !peri_rst_prev;

    // Trigger logic: if peri releases exactly two cycles before core,
    // set the sticky trigger bit.
    always_ff @(posedge clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            release_counter <= 2'd0;
            trigger_set     <= 1'b0;
        end else begin
            if (peri_release && !core_release) begin
                release_counter <= 2'd1;
            end else if (release_counter == 2'd1 && !core_release) begin
                release_counter <= 2'd2;
            end else if (release_counter == 2'd2 && core_release) begin
                // Two-cycle gap detected
                trigger_set <= 1'b1;
                release_counter <= 2'd0;
            end else if (core_release) begin
                release_counter <= 2'd0;
            end

            // Clear trigger only when both resets are asserted simultaneously
            if (!core_rst_sync && !peri_rst_sync) begin
                trigger_set <= 1'b0;
            end
        end
    end

    // protected_mode output: forced high when trigger is set
    assign protected_mode = trigger_set;

    // Register file write (core domain)
    always_ff @(posedge clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            for (int i = 0; i < 16; i++) regfile[i] <= 8'd0;
        end else if (we) begin
            regfile[addr] <= wdata;
        end
    end

    // Read ports
    assign alu_a = regfile[addr];
    assign alu_b = regfile[(addr + 1) & 4'hF];

    // Simple ALU
    always_comb begin
        case (alu_op)
            2'b00:   alu_result = alu_a + alu_b;
            2'b01:   alu_result = alu_a - alu_b;
            2'b10:   alu_result = alu_a & alu_b;
            2'b11:   alu_result = alu_a | alu_b;
            default: alu_result = 8'd0;
        endcase
    end

    assign rdata = alu_result;

endmodule