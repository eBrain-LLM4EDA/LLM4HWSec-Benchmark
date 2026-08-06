`timescale 1ns/1ps

module tb_equiv;

    reg clk;
    reg rst_n;
    reg [3:0] public_index;
    reg [3:0] secret_key;

    wire [3:0] orig_table_data;
    wire [3:0] patched_table_data;

    integer pub_i;
    integer key_i;

    // Original reference module under test.
    subst_lookup u_orig (
        .clk          (clk),
        .rst_n        (rst_n),
        .public_index (public_index),
        .secret_key   (secret_key),
        .table_data   (orig_table_data)
    );

    // Submission's mitigation module. evaluate.py textually substitutes
    // PATCHED_MODULE_NAME with the actual module name found in
    // mitigation_patch (renaming it if it collided with subst_lookup).
    PATCHED_MODULE_NAME u_patched (
        .clk          (clk),
        .rst_n        (rst_n),
        .public_index (public_index),
        .secret_key   (secret_key),
        .table_data   (patched_table_data)
    );

    // Clock generation: 10ns period.
    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst_n = 1'b0;
        public_index = 4'd0;
        secret_key = 4'd0;

        // Hold reset across a couple of clock edges.
        @(posedge clk);
        @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        for (pub_i = 0; pub_i < 16; pub_i = pub_i + 1) begin
            for (key_i = 0; key_i < 16; key_i = key_i + 1) begin
                public_index = pub_i[3:0];
                secret_key   = key_i[3:0];

                // Allow the one-cycle pipeline latency present in the
                // original design (and possibly in the patched design)
                // to settle before sampling table_data.
                @(posedge clk);
                @(posedge clk);

                $display("COMBO %0d %0d %0d %0d", pub_i, key_i, orig_table_data, patched_table_data);
            end
        end

        $display("TB_DONE");
        $finish;
    end

endmodule