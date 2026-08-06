module flattened_netlist (
  input  [6:0] codeword,
  output [3:0] data,
  output [6:0] corrected_codeword,
  output       error_detected
);

  wire n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11, n12;
  wire _T_1, _T_2, _T_3;
  wire [2:0] n_syn;
  wire [7:1] n_flip;

  // --- opaque XOR fan-in trees (syndrome computation) ---
  xor (n1, codeword[0], codeword[2]);
  xor (n2, codeword[4], codeword[6]);
  xor (_T_1, n1, n2);

  xor (n3, codeword[1], codeword[2]);
  xor (n4, codeword[5], codeword[6]);
  xor (_T_2, n3, n4);

  xor (n5, codeword[3], codeword[4]);
  xor (n6, codeword[5], codeword[6]);
  xor (_T_3, n5, n6);

  assign n_syn[0] = _T_1;
  assign n_syn[1] = _T_2;
  assign n_syn[2] = _T_3;

  assign error_detected = n_syn[0] | n_syn[1] | n_syn[2];

  // --- decode syndrome (1-indexed bit position) into one-hot flip mask ---
  assign n_flip[1] = (n_syn == 3'd1);
  assign n_flip[2] = (n_syn == 3'd2);
  assign n_flip[3] = (n_syn == 3'd3);
  assign n_flip[4] = (n_syn == 3'd4);
  assign n_flip[5] = (n_syn == 3'd5);
  assign n_flip[6] = (n_syn == 3'd6);
  assign n_flip[7] = (n_syn == 3'd7);

  // --- apply flip mask to obtain corrected codeword ---
  wire n7a, n8a, n9a, n10a, n11a, n12a, n13a;
  xor (n7a,  codeword[0], n_flip[1]);
  xor (n8a,  codeword[1], n_flip[2]);
  xor (n9a,  codeword[2], n_flip[3]);
  xor (n10a, codeword[3], n_flip[4]);
  xor (n11a, codeword[4], n_flip[5]);
  xor (n12a, codeword[5], n_flip[6]);
  xor (n13a, codeword[6], n_flip[7]);

  assign corrected_codeword[0] = n7a;
  assign corrected_codeword[1] = n8a;
  assign corrected_codeword[2] = n9a;
  assign corrected_codeword[3] = n10a;
  assign corrected_codeword[4] = n11a;
  assign corrected_codeword[5] = n12a;
  assign corrected_codeword[6] = n13a;

  // --- extract recovered data word from corrected codeword ---
  wire n14, n15, n16, n17;
  buf (n14, corrected_codeword[6]);
  buf (n15, corrected_codeword[5]);
  buf (n16, corrected_codeword[4]);
  buf (n17, corrected_codeword[2]);

  assign data[3] = n14;
  assign data[2] = n15;
  assign data[1] = n16;
  assign data[0] = n17;

endmodule