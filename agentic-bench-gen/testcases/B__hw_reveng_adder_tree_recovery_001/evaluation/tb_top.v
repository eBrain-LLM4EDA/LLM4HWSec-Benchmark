`timescale 1ns/1ps

module tb_top;

    reg  [15:0] a, b, c, d;
    wire [31:0] sum_rec;
    wire [31:0] sum_ref;

    recovered_design DUT_REC (
        .a(a),
        .b(b),
        .c(c),
        .d(d),
        .sum(sum_rec)
    );

    reference_design DUT_REF (
        .a(a),
        .b(b),
        .c(c),
        .d(d),
        .sum(sum_ref)
    );

    integer fd;
    integer count;
    integer idx;
    integer code;
    reg [1023:0] vecfile;

    initial begin
        if (!$value$plusargs("VECFILE=%s", vecfile)) begin
            $display("VEC_ERROR no VECFILE plusarg supplied");
            $finish;
        end

        fd = $fopen(vecfile, "r");
        if (fd == 0) begin
            $display("VEC_ERROR could not open vector file");
            $finish;
        end

        code = $fscanf(fd, "%d\n", count);

        for (idx = 0; idx < count; idx = idx + 1) begin
            code = $fscanf(fd, "%h %h %h %h\n", a, b, c, d);
            #1;
            $display("VEC %0d %08h %08h", idx, sum_rec, sum_ref);
        end

        $display("VEC_DONE %0d", count);

        $fclose(fd);
        $finish;
    end

endmodule