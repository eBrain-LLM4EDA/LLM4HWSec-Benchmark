module recovered_decoder (
  input  [6:0] codeword,
  output [3:0] data,
  output [6:0] corrected_codeword,
  output       error_detected
);

  // Syndrome bits: recompute the three parity checks against the
  // received codeword. Parity positions (1-indexed) are 1, 2, 4;
  // s0 covers positions {1,3,5,7}, s1 covers {2,3,6,7}, s2 covers {4,5,6,7}.
  wire s0 = codeword[0] ^ codeword[2] ^ codeword[4] ^ codeword[6];
  wire s1 = codeword[1] ^ codeword[2] ^ codeword[5] ^ codeword[6];
  wire s2 = codeword[3] ^ codeword[4] ^ codeword[5] ^ codeword[6];

  // Syndrome as a 3-bit binary number {s2,s1,s0} gives the 1-indexed
  // bit position of the single erroneous bit (0 = no error).
  wire [2:0] syndrome = {s2, s1, s0};

  assign error_detected = s0 | s1 | s2;

  // Flip the bit at the position indicated by the syndrome (if nonzero).
  assign corrected_codeword[0] = codeword[0] ^ (syndrome == 3'd1);
  assign corrected_codeword[1] = codeword[1] ^ (syndrome == 3'd2);
  assign corrected_codeword[2] = codeword[2] ^ (syndrome == 3'd3);
  assign corrected_codeword[3] = codeword[3] ^ (syndrome == 3'd4);
  assign corrected_codeword[4] = codeword[4] ^ (syndrome == 3'd5);
  assign corrected_codeword[5] = codeword[5] ^ (syndrome == 3'd6);
  assign corrected_codeword[6] = codeword[6] ^ (syndrome == 3'd7);

  // Recovered data word extracted from corrected codeword's data
  // positions 7, 6, 5, 3 (1-indexed), i.e. corrected_codeword[6,5,4,2].
  assign data[3] = corrected_codeword[6];
  assign data[2] = corrected_codeword[5];
  assign data[1] = corrected_codeword[4];
  assign data[0] = corrected_codeword[2];

endmodule