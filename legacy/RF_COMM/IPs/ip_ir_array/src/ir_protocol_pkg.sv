package ir_protocol_pkg;
  parameter logic [7:0] IRP_SOF       = 8'hA5;
  parameter logic [3:0] IRP_VERSION   = 4'h1;
  parameter logic [3:0] IRP_TYPE_DATA = 4'h1;
  parameter logic [3:0] IRP_TYPE_ACK  = 4'h2;

  // DATA frame header layout:
  //  0: SOF
  //  1: {version, type}
  //  2: session_id[7:0]
  //  3: session_id[15:8]
  //  4: pkt_seq[7:0]
  //  5: pkt_seq[15:8]
  //  6: frag_idx
  //  7: frag_count
  //  8: total_len[7:0]
  //  9: total_len[15:8]
  // 10: payload_len
  // 11: reserved (must be 0 in this revision)
  // 12: header_crc16[7:0]
  // 13: header_crc16[15:8]
  parameter int IRP_DATA_HDR_BYTES = 14;

  // ACK frame header layout:
  //  0: SOF
  //  1: {version, type}
  //  2: session_id[7:0]
  //  3: session_id[15:8]
  //  4: pkt_seq[7:0]
  //  5: pkt_seq[15:8]
  //  6: frag_count
  //  7: bitmap_bytes
  //  8: {7'd0, complete}
  //  9: reserved
  // 10: header_crc16[7:0]
  // 11: header_crc16[15:8]
  parameter int IRP_ACK_HDR_BYTES  = 12;
  parameter int IRP_MAX_FRAGS_FIELD = 255;

  function automatic logic [31:0] crc32_next_byte(
    input logic [7:0]  data,
    input logic [31:0] crc_in
  );
    logic [31:0] c;
    int i;
    begin
      c = crc_in ^ {24'h0, data};
      for (i = 0; i < 8; i = i + 1) begin
        if (c[0]) c = (c >> 1) ^ 32'hEDB88320;
        else      c = (c >> 1);
      end
      crc32_next_byte = c;
    end
  endfunction

  function automatic logic [15:0] crc16_ccitt_next_byte(
    input logic [7:0]  data,
    input logic [15:0] crc_in
  );
    logic [15:0] c;
    logic [7:0]  d;
    int i;
    begin
      c = crc_in;
      d = data;
      for (i = 0; i < 8; i = i + 1) begin
        if (c[15] ^ d[7]) c = {c[14:0], 1'b0} ^ 16'h1021;
        else              c = {c[14:0], 1'b0};
        d = {d[6:0], 1'b0};
      end
      crc16_ccitt_next_byte = c;
    end
  endfunction

  function automatic logic [31:0] ones_mask32(input int nbits);
    logic [31:0] m;
    int i;
    begin
      m = 32'h0;
      for (i = 0; i < 32; i = i + 1) begin
        if (i < nbits) m[i] = 1'b1;
      end
      ones_mask32 = m;
    end
  endfunction
endpackage
