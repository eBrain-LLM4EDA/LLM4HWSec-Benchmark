// =============================================================================
// evaluation/tb_cycle_count.v
//
// Reference testbench used by evaluate.py to independently characterize the
// cycle-count behavior of scalar_mult_ctrl.v as a function of the input
// scalar. This testbench is NOT graded; it exists purely to produce an
// independent (scalar, cycle_count, result_x, result_y) reference table
// that evaluate.py cross-checks the submitted vulnerability_report.json
// against.
//
// Scalar list is read, one 16-bit decimal value per line, from a file whose
// path defaults to "evaluation/private/scalar_input.txt" but can be
// overridden with +SCALAR_FILE=<path> on the vvp command line.
//
// For each scalar: pulse start for one cycle while idle, wait for
// cycle_count_valid, then print:
//   CYCLE_RESULT <scalar_decimal> <cycle_count_decimal>
//   RESULT_XY <scalar_decimal> <result_x_hex> <result_y_hex>
// =============================================================================

`timescale 1ns/1ps

module tb_cycle_count;

    reg         clk;
    reg         rst_n;
    reg         start;
    reg  [15:0] scalar;

    wire        done;
    wire [63:0] result_x;
    wire [63:0] result_y;
    wire [2:0]  state;
    wire [15:0] cycle_count;
    wire        cycle_count_valid;

    scalar_mult_ctrl dut (
        .clk               (clk),
        .rst_n             (rst_n),
        .start             (start),
        .scalar            (scalar),
        .done              (done),
        .result_x          (result_x),
        .result_y          (result_y),
        .state             (state),
        .cycle_count       (cycle_count),
        .cycle_count_valid (cycle_count_valid)
    );

    // -------------------------------------------------------------------
    // Clock generation
    // -------------------------------------------------------------------
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // -------------------------------------------------------------------
    // Scalar list storage
    // -------------------------------------------------------------------
    localparam MAX_SCALARS = 256;
    reg [15:0] scalar_list [0:MAX_SCALARS-1];
    integer    num_scalars;

    // -------------------------------------------------------------------
    // File reading
    // -------------------------------------------------------------------
    integer fd;
    integer scan_ok;
    integer tmp_val;
    reg [1023:0] scalar_file_path;

    integer i;
    integer timeout_ctr;

    initial begin
        // Determine scalar file path: allow override via +SCALAR_FILE=,
        // default to the fixed reference scalar list.
        if (!$value$plusargs("SCALAR_FILE=%s", scalar_file_path)) begin
            scalar_file_path = "evaluation/private/scalar_input.txt";
        end

        fd = $fopen(scalar_file_path, "r");
        if (fd == 0) begin
            $display("ERROR: could not open scalar file %s", scalar_file_path);
            $finish;
        end

        num_scalars = 0;
        while (!$feof(fd) && num_scalars < MAX_SCALARS) begin
            scan_ok = $fscanf(fd, "%d\n", tmp_val);
            if (scan_ok == 1) begin
                scalar_list[num_scalars] = tmp_val[15:0];
                num_scalars = num_scalars + 1;
            end
        end
        $fclose(fd);

        // -----------------------------------------------------------
        // Reset sequence
        // -----------------------------------------------------------
        rst_n  = 1'b0;
        start  = 1'b0;
        scalar = 16'd0;

        @(posedge clk);
        @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        // -----------------------------------------------------------
        // Drive each scalar sequentially
        // -----------------------------------------------------------
        for (i = 0; i < num_scalars; i = i + 1) begin
            // Ensure controller is idle (state 0 / IDLE) before pulsing start.
            // Wait a cycle boundary, then apply scalar and pulse start.
            @(posedge clk);
            scalar = scalar_list[i];
            start  = 1'b1;
            @(posedge clk);
            start  = 1'b0;

            // Wait for cycle_count_valid (coincident with done), with a
            // generous timeout to avoid hanging forever on a broken DUT.
            timeout_ctr = 0;
            while (!cycle_count_valid && timeout_ctr < 100000) begin
                @(posedge clk);
                timeout_ctr = timeout_ctr + 1;
            end

            if (!cycle_count_valid) begin
                $display("ERROR: timeout waiting for cycle_count_valid for scalar %0d", scalar_list[i]);
            end else begin
                $display("CYCLE_RESULT %0d %0d", scalar_list[i], cycle_count);
                $display("RESULT_XY %0d %h %h", scalar_list[i], result_x, result_y);
            end

            // Allow one extra cycle so done/cycle_count_valid pulses clear
            // before the next start pulse.
            @(posedge clk);
        end

        $display("DONE_ALL");
        $finish;
    end

    // -------------------------------------------------------------------
    // Safety timeout in case something hangs unexpectedly
    // -------------------------------------------------------------------
    initial begin
        #2000000;
        $display("ERROR: global testbench timeout");
        $finish;
    end

endmodule