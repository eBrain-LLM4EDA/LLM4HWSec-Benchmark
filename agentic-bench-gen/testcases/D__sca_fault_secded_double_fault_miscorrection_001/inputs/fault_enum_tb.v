`timescale 1ns/1ps

module fault_enum_tb;

    reg  [7:0]  data_in;
    reg         encode_en;
    reg  [12:0] codeword_in;
    wire [12:0] codeword_out;
    wire [7:0]  data_out;
    wire [3:0]  syndrome;
    wire        overall_parity_error;
    wire        correctable;
    wire        uncorrectable;
    wire [12:0] correction_mask;

    secded_codec dut (
        .data_in(data_in),
        .encode_en(encode_en),
        .codeword_in(codeword_in),
        .codeword_out(codeword_out),
        .data_out(data_out),
        .syndrome(syndrome),
        .overall_parity_error(overall_parity_error),
        .correctable(correctable),
        .uncorrectable(uncorrectable),
        .correction_mask(correction_mask)
    );

    // Fixed reference codeword corresponding to reference data_in = 8'b10110010,
    // matching inputs/fault_model.json's reference_codeword (bit-vector notation,
    // i.e. this is the value that would appear on codeword_out for that data_in).
    reg [12:0] ref_codeword;

    integer i, j;
    integer idx;
    reg [12:0] faulted;

    task apply_and_report;
        input [127:0] label; // up to 16 ASCII chars, printed as string
        begin
            codeword_in = faulted;
            #1;
            $display("case=%0d id=%0s syndrome=%b overall_parity_error=%b correctable=%b uncorrectable=%b correction_mask=%b data_out=%b",
                      idx, label, syndrome, overall_parity_error, correctable, uncorrectable, correction_mask, data_out);
            idx = idx + 1;
        end
    endtask

    initial begin
        // Derive the reference codeword by running the encoder once on the
        // fixed reference data value, rather than hardcoding a separately
        // computed constant.
        data_in   = 8'b10110010;
        encode_en = 1'b1;
        codeword_in = 13'b0;
        #1;
        ref_codeword = codeword_out;

        encode_en = 1'b0;
        idx = 0;

        $display("REFERENCE codeword_out(data_in=8'b10110010)=%b", ref_codeword);
        $display("--- single-bit faults ---");

        for (i = 0; i <= 12; i = i + 1) begin
            faulted = ref_codeword ^ (13'b1 << i);
            apply_and_report({"single_", "b"});
        end

        $display("--- two-bit faults ---");

        for (i = 0; i <= 12; i = i + 1) begin
            for (j = i + 1; j <= 12; j = j + 1) begin
                faulted = ref_codeword ^ (13'b1 << i) ^ (13'b1 << j);
                apply_and_report({"double_", "b"});
            end
        end

        $display("TOTAL_CASES=%0d", idx);
        $finish;
    end

endmodule