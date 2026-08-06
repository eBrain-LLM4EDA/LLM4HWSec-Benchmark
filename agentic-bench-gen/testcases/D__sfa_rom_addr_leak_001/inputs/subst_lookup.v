module subst_lookup(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [3:0] public_index,
    input  wire [3:0] secret_key,
    output wire [3:0] table_data
);

    wire [3:0] lookup_index;
    reg  [3:0] rom_addr_q;
    reg  [3:0] table_data_r;

    assign lookup_index = public_index ^ secret_key;

    always @(posedge clk) begin
        if (!rst_n)
            rom_addr_q <= 4'd0;
        else
            rom_addr_q <= lookup_index;
    end

    always @(*) begin
        case (rom_addr_q)
            4'd0:  table_data_r = 4'd9;
            4'd1:  table_data_r = 4'd4;
            4'd2:  table_data_r = 4'd15;
            4'd3:  table_data_r = 4'd0;
            4'd4:  table_data_r = 4'd11;
            4'd5:  table_data_r = 4'd6;
            4'd6:  table_data_r = 4'd2;
            4'd7:  table_data_r = 4'd13;
            4'd8:  table_data_r = 4'd5;
            4'd9:  table_data_r = 4'd10;
            4'd10: table_data_r = 4'd1;
            4'd11: table_data_r = 4'd14;
            4'd12: table_data_r = 4'd7;
            4'd13: table_data_r = 4'd8;
            4'd14: table_data_r = 4'd3;
            4'd15: table_data_r = 4'd12;
            default: table_data_r = 4'd0;
        endcase
    end

    assign table_data = table_data_r;

endmodule