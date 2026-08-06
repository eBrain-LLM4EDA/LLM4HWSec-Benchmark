# Private whitelist of legitimate scan-control node names.
# These nodes are part of the documented DFT infrastructure and must never
# be flagged as Trojan trigger or payload nodes.

SCAN_WHITELIST = {
    # Top-level ports
    "test_mode",
    "scan_in",
    "scan_out",
    "clk",
    "rst_n",
    "data_in",
    "data_out",

    # Internal scan-control signals
    "scan_enable",

    # Scan multiplexer outputs (bit indices 0-3)
    "scan_mux_out[0]",
    "scan_mux_out[1]",
    "scan_mux_out[2]",
    "scan_mux_out[3]",

    # DFF outputs (bit indices 0-3)
    "dff_q[0]",
    "dff_q[1]",
    "dff_q[2]",
    "dff_q[3]",

    # Scan chain wires (declared but unused in this clean netlist)
    "next_scan_chain[0]",
    "next_scan_chain[1]",
    "next_scan_chain[2]",
    "next_scan_chain[3]",
    "scan_chain[0]",
    "scan_chain[1]",
    "scan_chain[2]",
    "scan_chain[3]",

    # DFF inputs (bit indices 0-3)
    "dff_d[0]",
    "dff_d[1]",
    "dff_d[2]",
    "dff_d[3]",

    # Instance names for scan-related primitives
    "u_scan_en_buf",
    "u_mux0",
    "u_mux1",
    "u_mux2",
    "u_mux3",
    "u_dff0",
    "u_dff1",
    "u_dff2",
    "u_dff3",
    "u_out0",
    "u_out1",
    "u_out2",
    "u_out3",
    "u_scan_out",
}