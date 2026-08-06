`timescale 1ns/1ps

module tb_probe;

    reg  [7:0] a_reg;
    reg  [7:0] b_reg;
    wire [15:0] p_wire;

    integer fd;
    integer code;
    reg [7:0] a_bits;
    reg [7:0] b_bits;

    mult8_top uut(.a(a_reg), .b(b_reg), .p(p_wire));

    task print_bin16;
        input [15:0] val;
        integer i;
        reg [127:0] s;
        begin
            s = "";
            for (i = 15; i >= 0; i = i - 1) begin
                if (val[i])
                    s = {s, "1"};
                else
                    s = {s, "0"};
            end
            $write("%0s", s);
        end
    endtask

    task print_bin8;
        input [7:0] val;
        integer i;
        reg [63:0] s;
        begin
            s = "";
            for (i = 7; i >= 0; i = i - 1) begin
                if (val[i])
                    s = {s, "1"};
                else
                    s = {s, "0"};
            end
            $write("%0s", s);
        end
    endtask

    initial begin
        fd = $fopen("vectors.txt", "r");
        if (fd == 0) begin
            $display("ERROR: could not open vectors.txt");
            $finish;
        end

        while (!$feof(fd)) begin
            code = $fscanf(fd, "%b %b\n", a_bits, b_bits);
            if (code == 2) begin
                a_reg = a_bits;
                b_reg = b_bits;
                #1;
                $write("VEC ");
                print_bin8(a_reg);
                $write(" ");
                print_bin8(b_reg);
                $write(" ");
                print_bin16(p_wire);
                $write("\n");
            end
        end

        $fclose(fd);
        $finish;
    end

endmodule