`timescale 1ns/1ps

module tb_top;

  reg  [6:0] codeword;

  wire [3:0] ref_data;
  wire [6:0] ref_corrected;
  wire       ref_error;

  wire [3:0] sub_data;
  wire [6:0] sub_corrected;
  wire       sub_error;

  integer i;

  flattened_netlist ref_inst (
    .codeword            (codeword),
    .data                (ref_data),
    .corrected_codeword  (ref_corrected),
    .error_detected      (ref_error)
  );

  recovered_decoder sub_inst (
    .codeword            (codeword),
    .data                (sub_data),
    .corrected_codeword  (sub_corrected),
    .error_detected      (sub_error)
  );

  initial begin
    for (i = 0; i < 128; i = i + 1) begin
      codeword = i[6:0];
      #5;
      $display("VEC %0d %b %b %b %b %b %b",
                codeword,
                ref_data, ref_corrected, ref_error,
                sub_data, sub_corrected, sub_error);
    end
    $finish;
  end

endmodule