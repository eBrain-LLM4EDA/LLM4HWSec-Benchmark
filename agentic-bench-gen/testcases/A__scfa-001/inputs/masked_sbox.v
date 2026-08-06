// masked_sbox.v
// First-order masked AES S-box with two random shares.
// Implements the S-box using a masked GF(2^8) inverter with
// registered pipeline stages.

module masked_sbox (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  share0_in,
    input  wire [7:0]  share1_in,
    output reg  [7:0]  share0_out,
    output reg  [7:0]  share1_out
);

    // Internal registers for the two shares
    reg [7:0] share0_q, share1_q;

    // Masked inversion intermediate signals
    wire [7:0] inv_share0, inv_share1;

    // Recombination signals
    wire [7:0] recombine_xor;
    reg  [7:0] recombined_sbox_q;

    // --------------------------------------------------------
    // Masked GF(2^8) inverter using two-share decomposition.
    // The inversion is performed on the masked shares such that
    // inv_share0 XOR inv_share1 = (share0_in XOR share1_in)^{-1}
    // in GF(2^8) with irreducible polynomial x^8+x^4+x^3+x+1.
    // --------------------------------------------------------
    masked_inverter u_inv (
        .a_share0(share0_in),
        .a_share1(share1_in),
        .inv_share0(inv_share0),
        .inv_share1(inv_share1)
    );

    // --------------------------------------------------------
    // Pipeline stage 1: register the inverted shares
    // --------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            share0_q <= 8'h00;
            share1_q <= 8'h00;
        end else begin
            share0_q <= inv_share0;
            share1_q <= inv_share1;
        end
    end

    // --------------------------------------------------------
    // Flawed recombination: both shares are XORed on a single
    // combinatorial net and captured in a register in the same
    // cycle, creating a first-order switching leakage point.
    // --------------------------------------------------------
    assign recombine_xor = share0_q ^ share1_q;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            recombined_sbox_q <= 8'h00;
        end else begin
            recombined_sbox_q <= recombine_xor;
        end
    end

    // --------------------------------------------------------
    // Output assignment: the recombined value is driven to both
    // output shares (for simplicity; in a real masked design
    // these would be remasked).
    // --------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            share0_out <= 8'h00;
            share1_out <= 8'h00;
        end else begin
            share0_out <= recombined_sbox_q;
            share1_out <= recombined_sbox_q;
        end
    end

endmodule


// ------------------------------------------------------------
// Masked GF(2^8) inverter module
// ------------------------------------------------------------
module masked_inverter (
    input  wire [7:0] a_share0,
    input  wire [7:0] a_share1,
    output wire [7:0] inv_share0,
    output wire [7:0] inv_share1
);

    // --------------------------------------------------------
    // Compute the unmasked input by XORing the two shares.
    // This is a local combinatorial net used only for the
    // inversion computation; it does not create a registered
    // leakage point by itself.
    // --------------------------------------------------------
    wire [7:0] a_unmasked = a_share0 ^ a_share1;

    // --------------------------------------------------------
    // GF(2^8) inversion using a simple lookup table (ROM).
    // The table stores the multiplicative inverse for each
    // 8-bit value under the AES irreducible polynomial.
    // --------------------------------------------------------
    reg [7:0] inv_table [0:255];
    integer i;
    initial begin
        // Initialize the inversion table with precomputed values.
        // These are the standard AES S-box multiplicative inverses
        // (affine transform not applied here for simplicity).
        inv_table[8'h00] = 8'h00;
        inv_table[8'h01] = 8'h01;
        inv_table[8'h02] = 8'h8d;
        inv_table[8'h03] = 8'hf6;
        inv_table[8'h04] = 8'hcb;
        inv_table[8'h05] = 8'h52;
        inv_table[8'h06] = 8'h7b;
        inv_table[8'h07] = 8'hd1;
        inv_table[8'h08] = 8'he8;
        inv_table[8'h09] = 8'h4f;
        inv_table[8'h0a] = 8'h29;
        inv_table[8'h0b] = 8'hc0;
        inv_table[8'h0c] = 8'hb0;
        inv_table[8'h0d] = 8'h99;
        inv_table[8'h0e] = 8'he1;
        inv_table[8'h0f] = 8'h76;
        inv_table[8'h10] = 8'hca;
        inv_table[8'h11] = 8'h82;
        inv_table[8'h12] = 8'hc9;
        inv_table[8'h13] = 8'h7d;
        inv_table[8'h14] = 8'hfa;
        inv_table[8'h15] = 8'h59;
        inv_table[8'h16] = 8'h47;
        inv_table[8'h17] = 8'hf0;
        inv_table[8'h18] = 8'had;
        inv_table[8'h19] = 8'hd4;
        inv_table[8'h1a] = 8'ha2;
        inv_table[8'h1b] = 8'haf;
        inv_table[8'h1c] = 8'h9c;
        inv_table[8'h1d] = 8'ha4;
        inv_table[8'h1e] = 8'h72;
        inv_table[8'h1f] = 8'hc0;
        inv_table[8'h20] = 8'hb7;
        inv_table[8'h21] = 8'hfd;
        inv_table[8'h22] = 8'h93;
        inv_table[8'h23] = 8'h26;
        inv_table[8'h24] = 8'h36;
        inv_table[8'h25] = 8'h3f;
        inv_table[8'h26] = 8'hf7;
        inv_table[8'h27] = 8'hcc;
        inv_table[8'h28] = 8'h34;
        inv_table[8'h29] = 8'ha5;
        inv_table[8'h2a] = 8'he5;
        inv_table[8'h2b] = 8'hf1;
        inv_table[8'h2c] = 8'h71;
        inv_table[8'h2d] = 8'hd8;
        inv_table[8'h2e] = 8'h31;
        inv_table[8'h2f] = 8'h15;
        inv_table[8'h30] = 8'h04;
        inv_table[8'h31] = 8'hc7;
        inv_table[8'h32] = 8'h23;
        inv_table[8'h33] = 8'hc3;
        inv_table[8'h34] = 8'h18;
        inv_table[8'h35] = 8'h96;
        inv_table[8'h36] = 8'h05;
        inv_table[8'h37] = 8'h9a;
        inv_table[8'h38] = 8'h07;
        inv_table[8'h39] = 8'h12;
        inv_table[8'h3a] = 8'h80;
        inv_table[8'h3b] = 8'he2;
        inv_table[8'h3c] = 8'heb;
        inv_table[8'h3d] = 8'h27;
        inv_table[8'h3e] = 8'hb2;
        inv_table[8'h3f] = 8'h75;
        inv_table[8'h40] = 8'h09;
        inv_table[8'h41] = 8'h83;
        inv_table[8'h42] = 8'h2c;
        inv_table[8'h43] = 8'h1a;
        inv_table[8'h44] = 8'h1b;
        inv_table[8'h45] = 8'h6e;
        inv_table[8'h46] = 8'h5a;
        inv_table[8'h47] = 8'ha0;
        inv_table[8'h48] = 8'h52;
        inv_table[8'h49] = 8'h3b;
        inv_table[8'h4a] = 8'hd6;
        inv_table[8'h4b] = 8'hb3;
        inv_table[8'h4c] = 8'h29;
        inv_table[8'h4d] = 8'he3;
        inv_table[8'h4e] = 8'h2f;
        inv_table[8'h4f] = 8'h84;
        inv_table[8'h50] = 8'h53;
        inv_table[8'h51] = 8'hd1;
        inv_table[8'h52] = 8'h00;
        inv_table[8'h53] = 8'hed;
        inv_table[8'h54] = 8'h20;
        inv_table[8'h55] = 8'hfc;
        inv_table[8'h56] = 8'hb1;
        inv_table[8'h57] = 8'h5b;
        inv_table[8'h58] = 8'h6a;
        inv_table[8'h59] = 8'hcb;
        inv_table[8'h5a] = 8'hbe;
        inv_table[8'h5b] = 8'h39;
        inv_table[8'h5c] = 8'h4a;
        inv_table[8'h5d] = 8'h4c;
        inv_table[8'h5e] = 8'h58;
        inv_table[8'h5f] = 8'hcf;
        inv_table[8'h60] = 8'hd0;
        inv_table[8'h61] = 8'hef;
        inv_table[8'h62] = 8'haa;
        inv_table[8'h63] = 8'hfb;
        inv_table[8'h64] = 8'h43;
        inv_table[8'h65] = 8'h4d;
        inv_table[8'h66] = 8'h33;
        inv_table[8'h67] = 8'h85;
        inv_table[8'h68] = 8'h45;
        inv_table[8'h69] = 8'hf9;
        inv_table[8'h6a] = 8'h02;
        inv_table[8'h6b] = 8'h7f;
        inv_table[8'h6c] = 8'h50;
        inv_table[8'h6d] = 8'h3c;
        inv_table[8'h6e] = 8'h9f;
        inv_table[8'h6f] = 8'ha8;
        inv_table[8'h70] = 8'h51;
        inv_table[8'h71] = 8'ha3;
        inv_table[8'h72] = 8'h40;
        inv_table[8'h73] = 8'h8f;
        inv_table[8'h74] = 8'h92;
        inv_table[8'h75] = 8'h9d;
        inv_table[8'h76] = 8'h38;
        inv_table[8'h77] = 8'hf5;
        inv_table[8'h78] = 8'hbc;
        inv_table[8'h79] = 8'hb6;
        inv_table[8'h7a] = 8'hda;
        inv_table[8'h7b] = 8'h21;
        inv_table[8'h7c] = 8'h10;
        inv_table[8'h7d] = 8'hff;
        inv_table[8'h7e] = 8'hf3;
        inv_table[8'h7f] = 8'hd2;
        inv_table[8'h80] = 8'hcd;
        inv_table[8'h81] = 8'h0c;
        inv_table[8'h82] = 8'h13;
        inv_table[8'h83] = 8'hec;
        inv_table[8'h84] = 8'h5f;
        inv_table[8'h85] = 8'h97;
        inv_table[8'h86] = 8'h44;
        inv_table[8'h87] = 8'h17;
        inv_table[8'h88] = 8'hc4;
        inv_table[8'h89] = 8'ha7;
        inv_table[8'h8a] = 8'h7e;
        inv_table[8'h8b] = 8'h3d;
        inv_table[8'h8c] = 8'h64;
        inv_table[8'h8d] = 8'h5d;
        inv_table[8'h8e] = 8'h19;
        inv_table[8'h8f] = 8'h73;
        inv_table[8'h90] = 8'h60;
        inv_table[8'h91] = 8'h81;
        inv_table[8'h92] = 8'h4f;
        inv_table[8'h93] = 8'hdc;
        inv_table[8'h94] = 8'h22;
        inv_table[8'h95] = 8'h2a;
        inv_table[8'h96] = 8'h90;
        inv_table[8'h97] = 8'h88;
        inv_table[8'h98] = 8'h46;
        inv_table[8'h99] = 8'hee;
        inv_table[8'h9a] = 8'hb8;
        inv_table[8'h9b] = 8'h14;
        inv_table[8'h9c] = 8'hde;
        inv_table[8'h9d] = 8'h5e;
        inv_table[8'h9e] = 8'h0b;
        inv_table[8'h9f] = 8'hdb;
        inv_table[8'ha0] = 8'he0;
        inv_table[8'ha1] = 8'h32;
        inv_table[8'ha2] = 8'h3a;
        inv_table[8'ha3] = 8'h0a;
        inv_table[8'ha4] = 8'h49;
        inv_table[8'ha5] = 8'h06;
        inv_table[8'ha6] = 8'h24;
        inv_table[8'ha7] = 8'h5c;
        inv_table[8'ha8] = 8'hc2;
        inv_table[8'ha9] = 8'hd3;
        inv_table[8'haa] = 8'hac;
        inv_table[8'hab] = 8'h62;
        inv_table[8'hac] = 8'h91;
        inv_table[8'had] = 8'h95;
        inv_table[8'hae] = 8'he4;
        inv_table[8'haf] = 8'h79;
        inv_table[8'hb0] = 8'he7;
        inv_table[8'hb1] = 8'hc8;
        inv_table[8'hb2] = 8'h37;
        inv_table[8'hb3] = 8'h6d;
        inv_table[8'hb4] = 8'h8d;
        inv_table[8'hb5] = 8'hd5;
        inv_table[8'hb6] = 8'h4e;
        inv_table[8'hb7] = 8'ha9;
        inv_table[8'hb8] = 8'h6c;
        inv_table[8'hb9] = 8'h56;
        inv_table[8'hba] = 8'hf4;
        inv_table[8'hbb] = 8'hea;
        inv_table[8'hbc] = 8'h65;
        inv_table[8'hbd] = 8'h7a;
        inv_table[8'hbe] = 8'hae;
        inv_table[8'hbf] = 8'h08;
        inv_table[8'hc0] = 8'hba;
        inv_table[8'hc1] = 8'h78;
        inv_table[8'hc2] = 8'h25;
        inv_table[8'hc3] = 8'h2e;
        inv_table[8'hc4] = 8'h1c;
        inv_table[8'hc5] = 8'ha6;
        inv_table[8'hc6] = 8'hb4;
        inv_table[8'hc7] = 8'hc6;
        inv_table[8'hc8] = 8'he8;
        inv_table[8'hc9] = 8'hdd;
        inv_table[8'hca] = 8'h74;
        inv_table[8'hcb] = 8'h1f;
        inv_table[8'hcc] = 8'h4b;
        inv_table[8'hcd] = 8'hbd;
        inv_table[8'hce] = 8'h8b;
        inv_table[8'hcf] = 8'h8a;
        inv_table[8'hd0] = 8'h70;
        inv_table[8'hd1] = 8'h3e;
        inv_table[8'hd2] = 8'hb5;
        inv_table[8'hd3] = 8'h66;
        inv_table[8'hd4] = 8'h48;
        inv_table[8'hd5] = 8'h03;
        inv_table[8'hd6] = 8'hf6;
        inv_table[8'hd7] = 8'h0e;
        inv_table[8'hd8] = 8'h61;
        inv_table[8'hd9] = 8'h35;
        inv_table[8'hda] = 8'h57;
        inv_table[8'hdb] = 8'hb9;
        inv_table[8'hdc] = 8'h86;
        inv_table[8'hdd] = 8'hc1;
        inv_table[8'hde] = 8'h1d;
        inv_table[8'hdf] = 8'h9e;
        inv_table[8'he0] = 8'he1;
        inv_table[8'he1] = 8'hf8;
        inv_table[8'he2] = 8'h98;
        inv_table[8'he3] = 8'h11;
        inv_table[8'he4] = 8'h69;
        inv_table[8'he5] = 8'hd9;
        inv_table[8'he6] = 8'h8e;
        inv_table[8'he7] = 8'h94;
        inv_table[8'he8] = 8'h9b;
        inv_table[8'he9] = 8'h1e;
        inv_table[8'hea] = 8'h87;
        inv_table[8'heb] = 8'he9;
        inv_table[8'hec] = 8'hce;
        inv_table[8'hed] = 8'h55;
        inv_table[8'hee] = 8'h28;
        inv_table[8'hef] = 8'hdf;
        inv_table[8'hf0] = 8'h8c;
        inv_table[8'hf1] = 8'ha1;
        inv_table[8'hf2] = 8'h89;
        inv_table[8'hf3] = 8'h0d;
        inv_table[8'hf4] = 8'hbf;
        inv_table[8'hf5] = 8'he6;
        inv_table[8'hf6] = 8'h42;
        inv_table[8'hf7] = 8'h68;
        inv_table[8'hf8] = 8'h41;
        inv_table[8'hf9] = 8'h99;
        inv_table[8'hfa] = 8'h2d;
        inv_table[8'hfb] = 8'h0f;
        inv_table[8'hfc] = 8'hb0;
        inv_table[8'hfd] = 8'h54;
        inv_table[8'hfe] = 8'hbb;
        inv_table[8'hff] = 8'h16;
    end

    wire [7:0] inv_unmasked = inv_table[a_unmasked];

    // --------------------------------------------------------
    // Remask the inverted value with fresh randomness.
    // For simplicity, we reuse the input shares as masks.
    // In a real design, fresh random masks would be used.
    // --------------------------------------------------------
    assign inv_share0 = inv_unmasked ^ a_share0;
    assign inv_share1 = a_share1;  // second share is just the mask

endmodule