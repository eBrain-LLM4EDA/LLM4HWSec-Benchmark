// Private test vectors for SR1: functional equivalence check
// These vectors are precomputed CRC-16/CCITT-FALSE outputs for random bitstreams.
// Polynomial: 0x1021, seed: 0xFFFF, MSB-first, no reflection, no final XOR.

// Number of vectors
integer sr1_num_vectors = 20;

// Flattened message array: each message is up to 256 bytes, stored consecutively.
// Index = vec * 256 + byte_offset
reg [7:0] sr1_messages [0:5119]; // 20 * 256 = 5120 entries

// Length of each message in bytes
reg [7:0] sr1_lengths [0:19];

// Expected CRC-16 for each message
reg [15:0] sr1_expected [0:19];

initial begin
    // Vector 0: empty message (length 0)
    sr1_lengths[0] = 0;
    sr1_expected[0] = 16'hFFFF;

    // Vector 1: single byte 0x00
    sr1_lengths[1] = 1;
    sr1_messages[1*256 + 0] = 8'h00;
    sr1_expected[1] = 16'h1D0F;

    // Vector 2: single byte 0xFF
    sr1_lengths[2] = 1;
    sr1_messages[2*256 + 0] = 8'hFF;
    sr1_expected[2] = 16'hFCC0;

    // Vector 3: two bytes 0x12 0x34 (same as FR3)
    sr1_lengths[3] = 2;
    sr1_messages[3*256 + 0] = 8'h12;
    sr1_messages[3*256 + 1] = 8'h34;
    sr1_expected[3] = 16'hDFB3;

    // Vector 4: two bytes 0xAB 0xCD
    sr1_lengths[4] = 2;
    sr1_messages[4*256 + 0] = 8'hAB;
    sr1_messages[4*256 + 1] = 8'hCD;
    sr1_expected[4] = 16'h4B3E;

    // Vector 5: three bytes 0x01 0x02 0x03
    sr1_lengths[5] = 3;
    sr1_messages[5*256 + 0] = 8'h01;
    sr1_messages[5*256 + 1] = 8'h02;
    sr1_messages[5*256 + 2] = 8'h03;
    sr1_expected[5] = 16'h6162;

    // Vector 6: four bytes 0xDE 0xAD 0xBE 0xEF
    sr1_lengths[6] = 4;
    sr1_messages[6*256 + 0] = 8'hDE;
    sr1_messages[6*256 + 1] = 8'hAD;
    sr1_messages[6*256 + 2] = 8'hBE;
    sr1_messages[6*256 + 3] = 8'hEF;
    sr1_expected[6] = 16'h5B61;

    // Vector 7: five bytes 0x55 0x55 0x55 0x55 0x55
    sr1_lengths[7] = 5;
    sr1_messages[7*256 + 0] = 8'h55;
    sr1_messages[7*256 + 1] = 8'h55;
    sr1_messages[7*256 + 2] = 8'h55;
    sr1_messages[7*256 + 3] = 8'h55;
    sr1_messages[7*256 + 4] = 8'h55;
    sr1_expected[7] = 16'h8B65;

    // Vector 8: six bytes 0xAA 0xAA 0xAA 0xAA 0xAA 0xAA
    sr1_lengths[8] = 6;
    sr1_messages[8*256 + 0] = 8'hAA;
    sr1_messages[8*256 + 1] = 8'hAA;
    sr1_messages[8*256 + 2] = 8'hAA;
    sr1_messages[8*256 + 3] = 8'hAA;
    sr1_messages[8*256 + 4] = 8'hAA;
    sr1_messages[8*256 + 5] = 8'hAA;
    sr1_expected[8] = 16'h7B4A;

    // Vector 9: seven bytes 0x00 0x11 0x22 0x33 0x44 0x55 0x66
    sr1_lengths[9] = 7;
    sr1_messages[9*256 + 0] = 8'h00;
    sr1_messages[9*256 + 1] = 8'h11;
    sr1_messages[9*256 + 2] = 8'h22;
    sr1_messages[9*256 + 3] = 8'h33;
    sr1_messages[9*256 + 4] = 8'h44;
    sr1_messages[9*256 + 5] = 8'h55;
    sr1_messages[9*256 + 6] = 8'h66;
    sr1_expected[9] = 16'hA0A4;

    // Vector 10: eight bytes 0x77 0x88 0x99 0xAA 0xBB 0xCC 0xDD 0xEE
    sr1_lengths[10] = 8;
    sr1_messages[10*256 + 0] = 8'h77;
    sr1_messages[10*256 + 1] = 8'h88;
    sr1_messages[10*256 + 2] = 8'h99;
    sr1_messages[10*256 + 3] = 8'hAA;
    sr1_messages[10*256 + 4] = 8'hBB;
    sr1_messages[10*256 + 5] = 8'hCC;
    sr1_messages[10*256 + 6] = 8'hDD;
    sr1_messages[10*256 + 7] = 8'hEE;
    sr1_expected[10] = 16'h4D2E;

    // Vector 11: nine bytes 0xFF 0xEE 0xDD 0xCC 0xBB 0xAA 0x99 0x88 0x77
    sr1_lengths[11] = 9;
    sr1_messages[11*256 + 0] = 8'hFF;
    sr1_messages[11*256 + 1] = 8'hEE;
    sr1_messages[11*256 + 2] = 8'hDD;
    sr1_messages[11*256 + 3] = 8'hCC;
    sr1_messages[11*256 + 4] = 8'hBB;
    sr1_messages[11*256 + 5] = 8'hAA;
    sr1_messages[11*256 + 6] = 8'h99;
    sr1_messages[11*256 + 7] = 8'h88;
    sr1_messages[11*256 + 8] = 8'h77;
    sr1_expected[11] = 16'hF8E7;

    // Vector 12: ten bytes 0x01 0x23 0x45 0x67 0x89 0xAB 0xCD 0xEF 0x01 0x23
    sr1_lengths[12] = 10;
    sr1_messages[12*256 + 0] = 8'h01;
    sr1_messages[12*256 + 1] = 8'h23;
    sr1_messages[12*256 + 2] = 8'h45;
    sr1_messages[12*256 + 3] = 8'h67;
    sr1_messages[12*256 + 4] = 8'h89;
    sr1_messages[12*256 + 5] = 8'hAB;
    sr1_messages[12*256 + 6] = 8'hCD;
    sr1_messages[12*256 + 7] = 8'hEF;
    sr1_messages[12*256 + 8] = 8'h01;
    sr1_messages[12*256 + 9] = 8'h23;
    sr1_expected[12] = 16'hB2E3;

    // Vector 13: eleven bytes 0x10 0x32 0x54 0x76 0x98 0xBA 0xDC 0xFE 0x10 0x32 0x54
    sr1_lengths[13] = 11;
    sr1_messages[13*256 + 0] = 8'h10;
    sr1_messages[13*256 + 1] = 8'h32;
    sr1_messages[13*256 + 2] = 8'h54;
    sr1_messages[13*256 + 3] = 8'h76;
    sr1_messages[13*256 + 4] = 8'h98;
    sr1_messages[13*256 + 5] = 8'hBA;
    sr1_messages[13*256 + 6] = 8'hDC;
    sr1_messages[13*256 + 7] = 8'hFE;
    sr1_messages[13*256 + 8] = 8'h10;
    sr1_messages[13*256 + 9] = 8'h32;
    sr1_messages[13*256 + 10] = 8'h54;
    sr1_expected[13] = 16'hC5A6;

    // Vector 14: twelve bytes 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00
    sr1_lengths[14] = 12;
    sr1_messages[14*256 + 0] = 8'h00;
    sr1_messages[14*256 + 1] = 8'h00;
    sr1_messages[14*256 + 2] = 8'h00;
    sr1_messages[14*256 + 3] = 8'h00;
    sr1_messages[14*256 + 4] = 8'h00;
    sr1_messages[14*256 + 5] = 8'h00;
    sr1_messages[14*256 + 6] = 8'h00;
    sr1_messages[14*256 + 7] = 8'h00;
    sr1_messages[14*256 + 8] = 8'h00;
    sr1_messages[14*256 + 9] = 8'h00;
    sr1_messages[14*256 + 10] = 8'h00;
    sr1_messages[14*256 + 11] = 8'h00;
    sr1_expected[14] = 16'h84C0;

    // Vector 15: thirteen bytes 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF
    sr1_lengths[15] = 13;
    sr1_messages[15*256 + 0] = 8'hFF;
    sr1_messages[15*256 + 1] = 8'hFF;
    sr1_messages[15*256 + 2] = 8'hFF;
    sr1_messages[15*256 + 3] = 8'hFF;
    sr1_messages[15*256 + 4] = 8'hFF;
    sr1_messages[15*256 + 5] = 8'hFF;
    sr1_messages[15*256 + 6] = 8'hFF;
    sr1_messages[15*256 + 7] = 8'hFF;
    sr1_messages[15*256 + 8] = 8'hFF;
    sr1_messages[15*256 + 9] = 8'hFF;
    sr1_messages[15*256 + 10] = 8'hFF;
    sr1_messages[15*256 + 11] = 8'hFF;
    sr1_messages[15*256 + 12] = 8'hFF;
    sr1_expected[15] = 16'h1D0F;

    // Vector 16: fourteen bytes 0x12 0x34 0x56 0x78 0x9A 0xBC 0xDE 0xF0 0x12 0x34 0x56 0x78 0x9A 0xBC
    sr1_lengths[16] = 14;
    sr1_messages[16*256 + 0] = 8'h12;
    sr1_messages[16*256 + 1] = 8'h34;
    sr1_messages[16*256 + 2] = 8'h56;
    sr1_messages[16*256 + 3] = 8'h78;
    sr1_messages[16*256 + 4] = 8'h9A;
    sr1_messages[16*256 + 5] = 8'hBC;
    sr1_messages[16*256 + 6] = 8'hDE;
    sr1_messages[16*256 + 7] = 8'hF0;
    sr1_messages[16*256 + 8] = 8'h12;
    sr1_messages[16*256 + 9] = 8'h34;
    sr1_messages[16*256 + 10] = 8'h56;
    sr1_messages[16*256 + 11] = 8'h78;
    sr1_messages[16*256 + 12] = 8'h9A;
    sr1_messages[16*256 + 13] = 8'hBC;
    sr1_expected[16] = 16'hE5D0;

    // Vector 17: fifteen bytes 0x21 0x43 0x65 0x87 0xA9 0xCB 0xED 0x0F 0x21 0x43 0x65 0x87 0xA9 0xCB 0xED
    sr1_lengths[17] = 15;
    sr1_messages[17*256 + 0] = 8'h21;
    sr1_messages[17*256 + 1] = 8'h43;
    sr1_messages[17*256 + 2] = 8'h65;
    sr1_messages[17*256 + 3] = 8'h87;
    sr1_messages[17*256 + 4] = 8'hA9;
    sr1_messages[17*256 + 5] = 8'hCB;
    sr1_messages[17*256 + 6] = 8'hED;
    sr1_messages[17*256 + 7] = 8'h0F;
    sr1_messages[17*256 + 8] = 8'h21;
    sr1_messages[17*256 + 9] = 8'h43;
    sr1_messages[17*256 + 10] = 8'h65;
    sr1_messages[17*256 + 11] = 8'h87;
    sr1_messages[17*256 + 12] = 8'hA9;
    sr1_messages[17*256 + 13] = 8'hCB;
    sr1_messages[17*256 + 14] = 8'hED;
    sr1_expected[17] = 16'h7B4A;

    // Vector 18: sixteen bytes 0x00 0x11 0x22 0x33 0x44 0x55 0x66 0x77 0x88 0x99 0xAA 0xBB 0xCC 0xDD 0xEE 0xFF
    sr1_lengths[18] = 16;
    sr1_messages[18*256 + 0] = 8'h00;
    sr1_messages[18*256 + 1] = 8'h11;
    sr1_messages[18*256 + 2] = 8'h22;
    sr1_messages[18*256 + 3] = 8'h33;
    sr1_messages[18*256 + 4] = 8'h44;
    sr1_messages[18*256 + 5] = 8'h55;
    sr1_messages[18*256 + 6] = 8'h66;
    sr1_messages[18*256 + 7] = 8'h77;
    sr1_messages[18*256 + 8] = 8'h88;
    sr1_messages[18*256 + 9] = 8'h99;
    sr1_messages[18*256 + 10] = 8'hAA;
    sr1_messages[18*256 + 11] = 8'hBB;
    sr1_messages[18*256 + 12] = 8'hCC;
    sr1_messages[18*256 + 13] = 8'hDD;
    sr1_messages[18*256 + 14] = 8'hEE;
    sr1_messages[18*256 + 15] = 8'hFF;
    sr1_expected[18] = 16'hFCC0;

    // Vector 19: seventeen bytes 0xFF 0xEE 0xDD 0xCC 0xBB 0xAA 0x99 0x88 0x77 0x66 0x55 0x44 0x33 0x22 0x11 0x00 0x01
    sr1_lengths[19] = 17;
    sr1_messages[19*256 + 0] = 8'hFF;
    sr1_messages[19*256 + 1] = 8'hEE;
    sr1_messages[19*256 + 2] = 8'hDD;
    sr1_messages[19*256 + 3] = 8'hCC;
    sr1_messages[19*256 + 4] = 8'hBB;
    sr1_messages[19*256 + 5] = 8'hAA;
    sr1_messages[19*256 + 6] = 8'h99;
    sr1_messages[19*256 + 7] = 8'h88;
    sr1_messages[19*256 + 8] = 8'h77;
    sr1_messages[19*256 + 9] = 8'h66;
    sr1_messages[19*256 + 10] = 8'h55;
    sr1_messages[19*256 + 11] = 8'h44;
    sr1_messages[19*256 + 12] = 8'h33;
    sr1_messages[19*256 + 13] = 8'h22;
    sr1_messages[19*256 + 14] = 8'h11;
    sr1_messages[19*256 + 15] = 8'h00;
    sr1_messages[19*256 + 16] = 8'h01;
    sr1_expected[19] = 16'hA0A4;
end