// testbench_regression.v
//
// Self-contained regression testbench for the 'controller' module.
// Drives a handful of representative functional stimulus vectors and
// prints data_out / secure_enable for manual inspection.

`timescale 1ns/1ps

module testbench_regression;

    reg        clk;
    reg        rst;
    reg        access_grant;
    reg        admin_override;
    reg        lock_bit;
    reg  [7:0] data_in;
    wire [7:0] data_out;
    wire       secure_enable;

    controller dut (
        .clk            (clk),
        .rst            (rst),
        .access_grant   (access_grant),
        .admin_override (admin_override),
        .lock_bit       (lock_bit),
        .data_in        (data_in),
        .data_out       (data_out),
        .secure_enable  (secure_enable)
    );

    // 10ns clock period
    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        $display("time\tacc\tadm\tlock\tdata_in\tdata_out\tsecure_enable");
        $monitor("%0t\t%b\t%b\t%b\t%h\t%h\t%b",
                  $time, access_grant, admin_override, lock_bit,
                  data_in, data_out, secure_enable);

        // Initialize and reset
        rst            = 1'b1;
        access_grant   = 1'b0;
        admin_override = 1'b0;
        lock_bit       = 1'b0;
        data_in        = 8'h00;
        @(posedge clk);
        @(posedge clk);
        rst = 1'b0;

        // Case 1: ordinary access, no override, no lock
        access_grant   = 1'b1;
        admin_override = 1'b0;
        lock_bit       = 1'b0;
        data_in        = 8'hA5;
        @(posedge clk);
        @(posedge clk);

        // Case 2: no access, admin override present but no grant
        access_grant   = 1'b0;
        admin_override = 1'b1;
        lock_bit       = 1'b0;
        data_in        = 8'h3C;
        @(posedge clk);
        @(posedge clk);

        // Case 3: full access and override together, unlocked
        access_grant   = 1'b1;
        admin_override = 1'b1;
        lock_bit       = 1'b0;
        data_in        = 8'hFF;
        @(posedge clk);
        @(posedge clk);

        // Case 4: neither access nor override, unlocked, idle data
        access_grant   = 1'b0;
        admin_override = 1'b0;
        lock_bit       = 1'b0;
        data_in        = 8'h00;
        @(posedge clk);
        @(posedge clk);

        // Case 5: brief reset pulse mid-stream, then resume ordinary traffic
        rst = 1'b1;
        @(posedge clk);
        rst = 1'b0;
        access_grant   = 1'b1;
        admin_override = 1'b0;
        lock_bit       = 1'b0;
        data_in        = 8'h5A;
        @(posedge clk);
        @(posedge clk);

        $display("Regression stimulus complete.");
        $finish;
    end

endmodule