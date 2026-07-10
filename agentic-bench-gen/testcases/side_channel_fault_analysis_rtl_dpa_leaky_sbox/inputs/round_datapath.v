// round_datapath.v
// Single-round substitution/permutation datapath.
// Pipeline: plaintext -> plaintext_reg -> key_mix_reg (XOR round_key)
//           -> sbox_out_reg (S-box lookup) -> round_out_reg (linear diffusion)

module round_datapath (
    input        clk,
    input        rst,
    input  [7:0] plaintext,
    input  [7:0] round_key,
    output [7:0] round_out
);

    reg [7:0] plaintext_reg;
    reg [7:0] key_mix_reg;
    reg [7:0] sbox_out_reg;
    reg [7:0] round_out_reg;

    wire [7:0] sbox_lookup_result;

    sbox_lut u_sbox_lut (
        .in  (key_mix_reg),
        .out (sbox_lookup_result)
    );

    always @(posedge clk) begin
        if (rst) begin
            plaintext_reg <= 8'h00;
        end else begin
            plaintext_reg <= plaintext;
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            key_mix_reg <= 8'h00;
        end else begin
            key_mix_reg <= plaintext_reg ^ round_key;
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            sbox_out_reg <= 8'h00;
        end else begin
            sbox_out_reg <= sbox_lookup_result;
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            round_out_reg <= 8'h00;
        end else begin
            round_out_reg <= ({sbox_out_reg[4:0], sbox_out_reg[7:5]}) ^ sbox_out_reg;
        end
    end

    assign round_out = round_out_reg;

endmodule