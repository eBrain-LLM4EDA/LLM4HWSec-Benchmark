`timescale 1ns/1ps

module testbench_reset_trace;

    reg        CLK;
    reg        RSTN;
    reg  [3:0] DIN;
    reg  [3:0] CTRL;
    wire [3:0] DOUT;

    integer cycle;

    top dut (
        .CLK  (CLK),
        .RSTN (RSTN),
        .DIN  (DIN),
        .CTRL (CTRL),
        .DOUT (DOUT)
    );

    initial CLK = 1'b0;
    always #5 CLK = ~CLK;

    initial begin
        cycle = 0;
        RSTN  = 1'b1;
        DIN   = 4'b0000;
        CTRL  = 4'b0000;

        @(negedge CLK);
        DIN  = 4'b1011;
        CTRL = 4'b1111;
        @(negedge CLK);
        CTRL = 4'b1010;
        DIN  = 4'b0111;
        @(negedge CLK);
        CTRL = 4'b1101;
        DIN  = 4'b1100;
        @(negedge CLK);
        CTRL = 4'b1001;
        DIN  = 4'b0110;
        @(negedge CLK);
        CTRL = 4'b1110;
        DIN  = 4'b1001;

        @(negedge CLK);
        $display("---- PRE-RESET STATE (cycle=%0d) ----", cycle);
        $display("ctrl_ff0=%b ctrl_ff1=%b ctrl_ff2=%b ctrl_ff3=%b dp_ff4=%b dp_ff5=%b priv_ff1=%b priv_ff2=%b",
                  dut.ctrl_ff0_q, dut.ctrl_ff1_q, dut.ctrl_ff2_q, dut.ctrl_ff3_q,
                  dut.dp_ff4_q,  dut.dp_ff5_q,
                  dut.priv_ff1_q, dut.priv_ff2_q);

        RSTN = 1'b0;
        @(negedge CLK);
        @(negedge CLK);
        @(negedge CLK);

        $display("---- DURING-RESET STATE (cycle=%0d) ----", cycle);
        $display("ctrl_ff0=%b ctrl_ff1=%b ctrl_ff2=%b ctrl_ff3=%b dp_ff4=%b dp_ff5=%b priv_ff1=%b priv_ff2=%b",
                  dut.ctrl_ff0_q, dut.ctrl_ff1_q, dut.ctrl_ff2_q, dut.ctrl_ff3_q,
                  dut.dp_ff4_q,  dut.dp_ff5_q,
                  dut.priv_ff1_q, dut.priv_ff2_q);

        RSTN = 1'b1;
        @(negedge CLK);

        $display("---- POST-RESET STATE (cycle=%0d) ----", cycle);
        $display("ctrl_ff0=%b ctrl_ff1=%b ctrl_ff2=%b ctrl_ff3=%b dp_ff4=%b dp_ff5=%b priv_ff1=%b priv_ff2=%b",
                  dut.ctrl_ff0_q, dut.ctrl_ff1_q, dut.ctrl_ff2_q, dut.ctrl_ff3_q,
                  dut.dp_ff4_q,  dut.dp_ff5_q,
                  dut.priv_ff1_q, dut.priv_ff2_q);

        repeat (30) begin
            @(negedge CLK);
        end

        $finish;
    end

    always @(posedge CLK) begin
        cycle = cycle + 1;
    end

    initial begin
        $monitor("t=%0t cycle=%0d RSTN=%b DIN=%b CTRL=%b DOUT=%b | ctrl_ff0=%b ctrl_ff1=%b ctrl_ff2=%b ctrl_ff3=%b dp_ff4=%b dp_ff5=%b priv_ff1=%b priv_ff2=%b",
                  $time, cycle, RSTN, DIN, CTRL, DOUT,
                  dut.ctrl_ff0_q, dut.ctrl_ff1_q, dut.ctrl_ff2_q, dut.ctrl_ff3_q,
                  dut.dp_ff4_q,  dut.dp_ff5_q,
                  dut.priv_ff1_q, dut.priv_ff2_q);
    end

endmodule