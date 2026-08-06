// evaluation/tb_top.v
// Exhaustive comparison testbench: reference netlist vs recovered RTL.
// No ports; self-contained top-level simulation driver.
//
// This testbench performs THREE independent, self-contained passes over
// the input space so that no requirement's PASS/FAIL determination can
// be masked or gated by another requirement's outcome:
//   Pass 1: global exhaustive sweep over all 8192 vectors -> TOTAL/MISMATCHES
//   Pass 2: dedicated mode=11 subset sweep                -> MODE11_*
//   Pass 3: dedicated mode=01/direction=0/MSB=1 subset sweep -> SR2_*
//
// Each pass re-drives the DUT/reference from scratch across its own
// vector set, so the SR2 counter in particular is not derived from, or
// contingent upon, the global tally in Pass 1.

`timescale 1ns/1ps

module tb_top;

    reg  [7:0] data_in;
    reg  [2:0] amount;
    reg        direction;
    reg  [1:0] mode;

    wire [7:0] ref_data_out;
    wire [7:0] dut_data_out;

    net_shifter_flat u_ref (
        .data_in   (data_in),
        .amount    (amount),
        .direction (direction),
        .mode      (mode),
        .data_out  (ref_data_out)
    );

    barrel_shifter_top u_dut (
        .data_in   (data_in),
        .amount    (amount),
        .direction (direction),
        .mode      (mode),
        .data_out  (dut_data_out)
    );

    integer i_data, i_amount, i_dir, i_mode;

    integer total_vectors;
    integer mismatches;
    integer first_mismatch_found;
    integer first_data_in, first_amount, first_direction, first_mode;

    integer mode11_mismatches;
    integer mode11_total;

    integer sr2_mismatches;
    integer sr2_total;

    initial begin
        // -------------------------------------------------------------
        // Pass 1: global exhaustive sweep (drives FR1-FR4)
        // -------------------------------------------------------------
        total_vectors        = 0;
        mismatches           = 0;
        first_mismatch_found = 0;
        first_data_in        = 0;
        first_amount         = 0;
        first_direction      = 0;
        first_mode           = 0;

        for (i_data = 0; i_data < 256; i_data = i_data + 1) begin
            for (i_amount = 0; i_amount < 8; i_amount = i_amount + 1) begin
                for (i_dir = 0; i_dir < 2; i_dir = i_dir + 1) begin
                    for (i_mode = 0; i_mode < 4; i_mode = i_mode + 1) begin
                        data_in   = i_data[7:0];
                        amount    = i_amount[2:0];
                        direction = i_dir[0:0];
                        mode      = i_mode[1:0];

                        #1;

                        total_vectors = total_vectors + 1;

                        if (ref_data_out !== dut_data_out) begin
                            mismatches = mismatches + 1;
                            if (first_mismatch_found == 0) begin
                                first_mismatch_found = 1;
                                first_data_in   = i_data;
                                first_amount    = i_amount;
                                first_direction = i_dir;
                                first_mode      = i_mode;
                            end
                            $display("MISMATCH data_in=%0d amount=%0d direction=%0d mode=%0d ref=%0d dut=%0d",
                                      i_data, i_amount, i_dir, i_mode, ref_data_out, dut_data_out);
                        end
                    end
                end
            end
        end

        if (first_mismatch_found == 0) begin
            $display("TOTAL_VECTORS=%0d MISMATCHES=%0d FIRST_MISMATCH=NONE",
                      total_vectors, mismatches);
        end else begin
            $display("TOTAL_VECTORS=%0d MISMATCHES=%0d FIRST_MISMATCH=%0d,%0d,%0d,%0d",
                      total_vectors, mismatches,
                      first_data_in, first_amount, first_direction, first_mode);
        end

        // -------------------------------------------------------------
        // Pass 2: dedicated mode=11 subset sweep (drives SR1)
        // Fully independent re-sweep; does not reuse Pass 1 counters.
        // -------------------------------------------------------------
        mode11_mismatches = 0;
        mode11_total      = 0;

        for (i_data = 0; i_data < 256; i_data = i_data + 1) begin
            for (i_amount = 0; i_amount < 8; i_amount = i_amount + 1) begin
                for (i_dir = 0; i_dir < 2; i_dir = i_dir + 1) begin
                    data_in   = i_data[7:0];
                    amount    = i_amount[2:0];
                    direction = i_dir[0:0];
                    mode      = 2'b11;

                    #1;

                    mode11_total = mode11_total + 1;
                    if (ref_data_out !== dut_data_out) begin
                        mode11_mismatches = mode11_mismatches + 1;
                    end
                end
            end
        end

        $display("MODE11_MISMATCHES=%0d MODE11_TOTAL=%0d", mode11_mismatches, mode11_total);

        // -------------------------------------------------------------
        // Pass 3: dedicated mode=01, direction=0, data_in[7]=1 subset
        // sweep (drives SR2). This is a standalone counter pass over
        // its own restricted vector set: it is NOT derived from, does
        // NOT reuse, and is NOT gated by Pass 1's mismatches counter or
        // by any other requirement's result. This line alone fully
        // determines SR2 PASS/FAIL.
        // -------------------------------------------------------------
        sr2_mismatches = 0;
        sr2_total      = 0;

        for (i_data = 128; i_data < 256; i_data = i_data + 1) begin
            // i_data ranges 128..255 => data_in[7] == 1 for all of these
            for (i_amount = 0; i_amount < 8; i_amount = i_amount + 1) begin
                data_in   = i_data[7:0];
                amount    = i_amount[2:0];
                direction = 1'b0;
                mode      = 2'b01;

                #1;

                sr2_total = sr2_total + 1;
                if (ref_data_out !== dut_data_out) begin
                    sr2_mismatches = sr2_mismatches + 1;
                end
            end
        end

        $display("SR2_MISMATCHES=%0d SR2_TOTAL=%0d", sr2_mismatches, sr2_total);

        $finish;
    end

endmodule