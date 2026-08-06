module secded_codec(
    input  wire [7:0]  data_in,
    input  wire        encode_en,
    input  wire [12:0] codeword_in,
    output wire [12:0] codeword_out,
    output wire [7:0]  data_out,
    output wire [3:0]  syndrome,
    output wire        overall_parity_error,
    output wire        correctable,
    output wire        uncorrectable,
    output wire [12:0] correction_mask
);

    // Bit layout (1-indexed positions mapped onto 0-indexed vector):
    // position 0  : overall/extended parity
    // position 1  : Hamming parity p1
    // position 2  : Hamming parity p2
    // position 3  : data d0
    // position 4  : Hamming parity p4
    // position 5  : data d1
    // position 6  : data d2
    // position 7  : data d3
    // position 8  : Hamming parity p8
    // position 9  : data d4
    // position 10 : data d5
    // position 11 : data d6
    // position 12 : data d7

    wire p1, p2, p4, p8, p0;
    wire [12:0] enc_word;

    // Encode path: build codeword from data_in
    assign p1 = data_in[0] ^ data_in[1] ^ data_in[3] ^ data_in[4] ^ data_in[6];
    assign p2 = data_in[0] ^ data_in[2] ^ data_in[3] ^ data_in[5] ^ data_in[6];
    assign p4 = data_in[1] ^ data_in[2] ^ data_in[3] ^ data_in[7];
    assign p8 = data_in[4] ^ data_in[5] ^ data_in[6] ^ data_in[7];

    assign enc_word[3]  = data_in[0];
    assign enc_word[5]  = data_in[1];
    assign enc_word[6]  = data_in[2];
    assign enc_word[7]  = data_in[3];
    assign enc_word[9]  = data_in[4];
    assign enc_word[10] = data_in[5];
    assign enc_word[11] = data_in[6];
    assign enc_word[12] = data_in[7];

    assign enc_word[1] = p1;
    assign enc_word[2] = p2;
    assign enc_word[4] = p4;
    assign enc_word[8] = p8;

    assign p0 = enc_word[1] ^ enc_word[2]  ^ enc_word[3]  ^ enc_word[4]  ^
                enc_word[5] ^ enc_word[6]  ^ enc_word[7]  ^ enc_word[8]  ^
                enc_word[9] ^ enc_word[10] ^ enc_word[11] ^ enc_word[12];

    assign enc_word[0] = p0;

    assign codeword_out = enc_word;

    // Decode path: analyze codeword_in
    wire s1, s2, s4, s8;

    assign s1 = codeword_in[1] ^ codeword_in[3] ^ codeword_in[5]  ^
                codeword_in[7] ^ codeword_in[9]  ^ codeword_in[11];

    assign s2 = codeword_in[2] ^ codeword_in[3] ^ codeword_in[6]  ^
                codeword_in[7] ^ codeword_in[10] ^ codeword_in[11];

    assign s4 = codeword_in[4] ^ codeword_in[5] ^ codeword_in[6]  ^
                codeword_in[7] ^ codeword_in[12];

    assign s8 = codeword_in[8] ^ codeword_in[9] ^ codeword_in[10] ^
                codeword_in[11] ^ codeword_in[12];

    assign syndrome = {s8, s4, s2, s1};

    assign overall_parity_error = codeword_in[0] ^ codeword_in[1]  ^ codeword_in[2]  ^
                                  codeword_in[3] ^ codeword_in[4]  ^ codeword_in[5]  ^
                                  codeword_in[6] ^ codeword_in[7]  ^ codeword_in[8]  ^
                                  codeword_in[9] ^ codeword_in[10] ^ codeword_in[11] ^
                                  codeword_in[12];

    assign correctable   = (syndrome != 4'b0000);
    assign uncorrectable = 1'b0;

    assign correction_mask = correctable ? (13'b1 << syndrome) : 13'b0;

    wire [12:0] corrected_word;
    assign corrected_word = codeword_in ^ correction_mask;

    assign data_out = { corrected_word[12], corrected_word[11], corrected_word[10],
                         corrected_word[9],  corrected_word[7],  corrected_word[6],
                         corrected_word[5],  corrected_word[3] };

endmodule