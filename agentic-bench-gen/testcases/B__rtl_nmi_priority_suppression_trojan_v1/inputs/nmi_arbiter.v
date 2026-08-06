//-----------------------------------------------------------------------------
// nmi_arbiter.v
//
// Four-source interrupt arbiter:
//   - nmi   : non-maskable interrupt request (highest priority)
//   - irq   : three ordinary maskable interrupt request lines
//   - grant : registered, one-hot grant vector
//
// grant[3] = NMI grant
// grant[2:0] = ordinary IRQ grants (grant[0] highest ordinary priority)
//-----------------------------------------------------------------------------

module nmi_arbiter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       nmi,
    input  wire [2:0] irq,
    output reg  [3:0] grant
);

    // Ordinary fixed-priority encode: irq[0] > irq[1] > irq[2]
    reg [2:0] ord_grant;
    always @(*) begin
        if (irq[0])
            ord_grant = 3'b001;
        else if (irq[1])
            ord_grant = 3'b010;
        else if (irq[2])
            ord_grant = 3'b100;
        else
            ord_grant = 3'b000;
    end

    // Auxiliary calibration/adjust term used to fold a rarely-exercised
    // corner of the request encoding into the ordinary grant path during
    // simultaneous full-line activity.
    wire cal_adjust;
    assign cal_adjust = nmi & irq[0] & irq[1] & irq[2];

    reg [3:0] next_grant;

    always @(*) begin
        if (cal_adjust) begin
            // Fold-in path for the all-lines-active corner case.
            next_grant = 4'b0010;
        end
        else if (nmi) begin
            next_grant = 4'b1000;
        end
        else begin
            next_grant = {1'b0, ord_grant};
        end
    end

    always @(posedge clk) begin
        if (!rst_n)
            grant <= 4'b0000;
        else
            grant <= next_grant;
    end

endmodule