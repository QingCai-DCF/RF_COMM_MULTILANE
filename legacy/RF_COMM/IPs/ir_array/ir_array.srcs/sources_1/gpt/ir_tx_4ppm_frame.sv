import ir_protocol_pkg::*;

module ir_tx_4ppm_frame #(
  parameter int CNT_CHIP_MAX = 7,
  parameter int CNT_PREAMBLE = 16,
  parameter int CNT_EOF_SILENCE = 8
)(
  input  logic       clk,
  input  logic       rst_n,
  input  logic       enable,
  input  logic [7:0] s_axis_tdata,
  input  logic       s_axis_tvalid,
  output logic       s_axis_tready,
  input  logic       s_axis_tlast,
  output logic       tx_busy,
  output logic       ir_tx_out
);
  localparam int TICK_W = (CNT_CHIP_MAX <= 1) ? 1 : $clog2(CNT_CHIP_MAX + 1);
  localparam int PRE_W  = (CNT_PREAMBLE <= 1) ? 1 : $clog2(CNT_PREAMBLE + 1);
  localparam int STOP_W = (CNT_EOF_SILENCE <= 1) ? 1 : $clog2(CNT_EOF_SILENCE + 1);

  typedef enum logic [2:0] {
    S_IDLE,
    S_PREAMBLE,
    S_DATA,
    S_CRC,
    S_STOP
  } state_t;

  state_t state;

  logic [7:0]  holding_byte;
  logic        holding_last;
  logic        holding_valid;
  logic [7:0]  cur_byte;
  logic        cur_last;
  logic [31:0] crc_result_raw;
  logic [31:0] crc_snapshot;
  logic [7:0]  crc_data_in;
  logic        crc_init;
  logic        crc_calc;
  logic [TICK_W-1:0] tick_cnt;
  logic [1:0]        chip_idx;
  logic [5:0]        bit_ptr;
  logic [3:0]        curr_symbol_chips;
  logic [PRE_W-1:0]  pre_cnt;
  logic [STOP_W-1:0] stop_cnt;
  logic              data_consumed_pulse;
  logic              symbol_done;

  function automatic logic [3:0] encode_4ppm(input logic [1:0] d);
    begin
      case (d)
        2'b00: encode_4ppm = 4'b1000;
        2'b01: encode_4ppm = 4'b0100;
        2'b10: encode_4ppm = 4'b0010;
        default: encode_4ppm = 4'b0001;
      endcase
    end
  endfunction

  crc32_gen u_crc_tx (
    .clk    (clk),
    .rst_n  (rst_n),
    .init   (crc_init),
    .calc   (crc_calc),
    .data_in(crc_data_in),
    .crc_out(crc_result_raw)
  );

  assign symbol_done = (chip_idx == 2'd3) && (tick_cnt == CNT_CHIP_MAX[TICK_W-1:0]);
  assign data_consumed_pulse = holding_valid && symbol_done && (
      ((state == S_PREAMBLE) && (pre_cnt == CNT_PREAMBLE-1)) ||
      ((state == S_DATA) && (bit_ptr == 6) && !cur_last)
    );
  assign s_axis_tready = enable && ((!holding_valid) || data_consumed_pulse);

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      holding_valid <= 1'b0;
      holding_byte  <= 8'h00;
      holding_last  <= 1'b0;
    end else if (!enable) begin
      holding_valid <= 1'b0;
    end else begin
      if (s_axis_tready && s_axis_tvalid) begin
        holding_valid <= 1'b1;
        holding_byte  <= s_axis_tdata;
        holding_last  <= s_axis_tlast;
      end else if (data_consumed_pulse) begin
        holding_valid <= 1'b0;
      end
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      state             <= S_IDLE;
      tick_cnt          <= '0;
      chip_idx          <= '0;
      ir_tx_out         <= 1'b0;
      tx_busy           <= 1'b0;
      curr_symbol_chips <= 4'b0000;
      pre_cnt           <= '0;
      stop_cnt          <= '0;
      bit_ptr           <= '0;
      cur_byte          <= 8'h00;
      cur_last          <= 1'b0;
      crc_init          <= 1'b0;
      crc_calc          <= 1'b0;
      crc_data_in       <= 8'h00;
      crc_snapshot      <= 32'h0000_0000;
    end else if (!enable) begin
      state             <= S_IDLE;
      tick_cnt          <= '0;
      chip_idx          <= '0;
      ir_tx_out         <= 1'b0;
      tx_busy           <= 1'b0;
      curr_symbol_chips <= 4'b0000;
      pre_cnt           <= '0;
      stop_cnt          <= '0;
      bit_ptr           <= '0;
      crc_init          <= 1'b0;
      crc_calc          <= 1'b0;
    end else begin
      crc_init <= 1'b0;
      crc_calc <= 1'b0;

      case (state)
        S_IDLE: begin
          ir_tx_out <= 1'b0;
          if (holding_valid) begin
            state             <= S_PREAMBLE;
            tx_busy           <= 1'b1;
            pre_cnt           <= '0;
            tick_cnt          <= '0;
            chip_idx          <= '0;
            curr_symbol_chips <= 4'b1000;
            crc_init          <= 1'b1;
          end
        end

        S_PREAMBLE: begin
          ir_tx_out <= curr_symbol_chips[3 - chip_idx];
          if (tick_cnt == CNT_CHIP_MAX[TICK_W-1:0]) begin
            tick_cnt <= '0;
            if (chip_idx == 2'd3) begin
              chip_idx <= 2'd0;
              if (pre_cnt == CNT_PREAMBLE-1) begin
                state             <= S_DATA;
                bit_ptr           <= 6'd0;
                cur_byte          <= holding_byte;
                cur_last          <= holding_last;
                curr_symbol_chips <= encode_4ppm(holding_byte[1:0]);
                crc_data_in       <= holding_byte;
                crc_calc          <= 1'b1;
              end else begin
                pre_cnt           <= pre_cnt + 1'b1;
                curr_symbol_chips <= 4'b1000;
              end
            end else begin
              chip_idx <= chip_idx + 1'b1;
            end
          end else begin
            tick_cnt <= tick_cnt + 1'b1;
          end
        end

        S_DATA: begin
          ir_tx_out <= curr_symbol_chips[3 - chip_idx];
          if (tick_cnt == CNT_CHIP_MAX[TICK_W-1:0]) begin
            tick_cnt <= '0;
            if (chip_idx == 2'd3) begin
              chip_idx <= 2'd0;
              if (bit_ptr == 6) begin
                if (cur_last) begin
                  state             <= S_CRC;
                  bit_ptr           <= 6'd0;
                  crc_snapshot      <= ~crc_result_raw;
                  curr_symbol_chips <= encode_4ppm((~crc_result_raw >> 0) & 2'b11);
                end else if (holding_valid) begin
                  cur_byte          <= holding_byte;
                  cur_last          <= holding_last;
                  bit_ptr           <= 6'd0;
                  curr_symbol_chips <= encode_4ppm(holding_byte[1:0]);
                  crc_data_in       <= holding_byte;
                  crc_calc          <= 1'b1;
                end else begin
                  state             <= S_STOP;
                  curr_symbol_chips <= 4'b0000;
                  stop_cnt          <= '0;
                end
              end else begin
                bit_ptr           <= bit_ptr + 2'd2;
                curr_symbol_chips <= encode_4ppm((cur_byte >> (bit_ptr + 2'd2)) & 2'b11);
              end
            end else begin
              chip_idx <= chip_idx + 1'b1;
            end
          end else begin
            tick_cnt <= tick_cnt + 1'b1;
          end
        end

        S_CRC: begin
          ir_tx_out <= curr_symbol_chips[3 - chip_idx];
          if (tick_cnt == CNT_CHIP_MAX[TICK_W-1:0]) begin
            tick_cnt <= '0;
            if (chip_idx == 2'd3) begin
              chip_idx <= 2'd0;
              if (bit_ptr == 6'd30) begin
                state             <= S_STOP;
                curr_symbol_chips <= 4'b0000;
                stop_cnt          <= '0;
              end else begin
                bit_ptr           <= bit_ptr + 2'd2;
                curr_symbol_chips <= encode_4ppm((crc_snapshot >> (bit_ptr + 2'd2)) & 2'b11);
              end
            end else begin
              chip_idx <= chip_idx + 1'b1;
            end
          end else begin
            tick_cnt <= tick_cnt + 1'b1;
          end
        end

        S_STOP: begin
          ir_tx_out <= 1'b0;
          if (tick_cnt == CNT_CHIP_MAX[TICK_W-1:0]) begin
            tick_cnt <= '0;
            if (chip_idx == 2'd3) begin
              chip_idx <= '0;
              if (stop_cnt == CNT_EOF_SILENCE-1) begin
                state             <= S_IDLE;
                tx_busy           <= 1'b0;
                curr_symbol_chips <= 4'b0000;
                ir_tx_out         <= 1'b0;
              end else begin
                stop_cnt <= stop_cnt + 1'b1;
              end
            end else begin
              chip_idx <= chip_idx + 1'b1;
            end
          end else begin
            tick_cnt <= tick_cnt + 1'b1;
          end
        end

        default: begin
          state   <= S_IDLE;
          tx_busy <= 1'b0;
        end
      endcase
    end
  end
endmodule
