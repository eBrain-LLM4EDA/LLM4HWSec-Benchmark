`timescale 1ns / 1ps

module tb_check;

    reg        clk;
    reg        rst_n;
    reg        load;
    reg [7:0]  data_in;
    wire [7:0] dbus;
    wire       valid;

    integer cycle_num;

    precharge_bus_wrapper dut (
        .clk     (clk),
        .rst_n   (rst_n),
        .load    (load),
        .data_in (data_in),
        .dbus    (dbus),
        .valid   (valid)
    );

    // 10ns period clock
    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        cycle_num = 0;
        rst_n     = 1'b0;
        load      = 1'b0;
        data_in   = 8'h00;

        // Hold reset for a couple of cycles
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        // Cycle offset 0: assert load with a known data word (0xA5,
        // Hamming weight 4) to exercise the precharge/evaluate sequence.
        data_in = 8'hA5;
        load    = 1'b1;
        @(negedge clk);
        cycle_num = cycle_num + 1;
        $display("CYCLE %0d LOAD=%0d DBUS=%02x VALID=%0d", cycle_num, load, dbus, valid);

        load = 1'b0;

        // Cycle offset +1: expected precharge phase
        @(negedge clk);
        cycle_num = cycle_num + 1;
        $display("CYCLE %0d LOAD=%0d DBUS=%02x VALID=%0d", cycle_num, load, dbus, valid);

        // Cycle offset +2: expected evaluate phase
        @(negedge clk);
        cycle_num = cycle_num + 1;
        $display("CYCLE %0d LOAD=%0d DBUS=%02x VALID=%0d", cycle_num, load, dbus, valid);

        // A couple more idle cycles for observation
        @(negedge clk);
        cycle_num = cycle_num + 1;
        $display("CYCLE %0d LOAD=%0d DBUS=%02x VALID=%0d", cycle_num, load, dbus, valid);

        @(negedge clk);
        cycle_num = cycle_num + 1;
        $display("CYCLE %0d LOAD=%0d DBUS=%02x VALID=%0d", cycle_num, load, dbus, valid);

        $finish;
    end

    // Safety timeout in case something hangs
    initial begin
        #1000;
        $finish;
    end

endmodule