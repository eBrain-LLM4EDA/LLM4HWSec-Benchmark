`timescale 1ns/1ps

module oracle_tb;

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

    reg [12:0] ref_codeword;
    integer i, j;
    reg [12:0] faulted;

    task apply_and_report_single;
        input integer bit_idx;
        begin
            faulted = ref_codeword ^ (13'b1 << bit_idx);
            codeword_in = faulted;
            #1;
            $display("FAULTID single_b%0d POS %0d SYN %b OPE %b CORR %b UNCORR %b MASK %b DOUT %b",
                      bit_idx, bit_idx, syndrome, overall_parity_error, correctable,
                      uncorrectable, correction_mask, data_out);
        end
    endtask

    task apply_and_report_double;
        input integer bit_i;
        input integer bit_j;
        begin
            faulted = ref_codeword ^ (13'b1 << bit_i) ^ (13'b1 << bit_j);
            codeword_in = faulted;
            #1;
            $display("FAULTID double_b%0d_b%0d POS %0d,%0d SYN %b OPE %b CORR %b UNCORR %b MASK %b DOUT %b",
                      bit_i, bit_j, bit_i, bit_j, syndrome, overall_parity_error, correctable,
                      uncorrectable, correction_mask, data_out);
        end
    endtask

    initial begin
        // Fixed reference data value, matching the same fixed reference
        // approach used by inputs/fault_enum_tb.v: derive the reference
        // codeword by running the encode path of the actual DUT once,
        // rather than hardcoding a separately computed codeword constant.
        data_in     = 8'b10110010;
        encode_en   = 1'b1;
        codeword_in = 13'b0;
        #1;
        ref_codeword = codeword_out;

        encode_en = 1'b0;

        $display("REFDATA %b", data_in);
        $display("REFCODEWORD %b", ref_codeword);

        for (i = 0; i <= 12; i = i + 1) begin
            apply_and_report_single(i);
        end

        for (i = 0; i <= 12; i = i + 1) begin
            for (j = i + 1; j <= 12; j = j + 1) begin
                apply_and_report_double(i, j);
            end
        end

        $display("TOTAL_CASES=91");
        $finish;
    end

endmodule