import ir_protocol_pkg::*;

module ir_rx_4ppm_frame #(
  parameter int MAX_FRAME_BYTES  = 64,
  parameter int CNT_CHIP_MAX     = 7,
  parameter int PREAMBLE_SYMS    = 16,
  parameter int EOF_SILENCE_SYMS = 3
)(
  input  logic       clk,
  input  logic       rst_n,
  input  logic       enable,
  input  logic       ir_rx_in,
  output logic [7:0] m_axis_tdata,
  output logic       m_axis_tvalid,
  input  logic       m_axis_tready,
  output logic       m_axis_tlast,
  output logic       rx_active,
  output logic       crc_error,
  output logic       overrun_error
);
  localparam int TICK_W = (CNT_CHIP_MAX <= 1) ? 1 : $clog2(CNT_CHIP_MAX + 1);
  localparam int PRE_W  = (PREAMBLE_SYMS <= 1) ? 1 : $clog2(PREAMBLE_SYMS + 1);
  localparam int BUF_BYTES = MAX_FRAME_BYTES + 4;
  localparam int BUF_W  = (BUF_BYTES <= 1) ? 1 : $clog2(BUF_BYTES + 1);

  typedef enum logic [2:0] {
    S_IDLE,
    S_PREAMBLE,
    S_DATA,
    S_CHECK,
    S_FLUSH
  } state_t;

  state_t state;
  logic r_in, r_in_d;
  logic rx_pulse_active;
  logic rx_rise_edge;
  logic [TICK_W-1:0] ticks;
  logic [1:0] chip_idx;
  logic [3:0] sym_capture;
  logic [7:0] shift_reg;
  logic [1:0] pair_cnt;
  logic [PRE_W-1:0] preamble_cnt;
  logic [7:0] silence_sym_cnt;
  logic [BUF_W-1:0] byte_cnt;
  logic [BUF_W-1:0] flush_ptr;
  logic [BUF_W-1:0] check_ptr;
  logic [31:0] crc_running;
  logic [BUF_W-1:0] payload_len;
  logic [7:0] rx_buf [0:BUF_BYTES-1];
  logic [2:0] dec_res;
  logic       sym_valid;
  logic [1:0] sym_val;
  logic [7:0] byte_assembled;
  integer i;

  function automatic logic [2:0] decode_ppm(input logic [3:0] s);
    begin
      case (s)
        4'b1000: decode_ppm = 3'b100;
        4'b0100: decode_ppm = 3'b101;
        4'b0010: decode_ppm = 3'b110;
        4'b0001: decode_ppm = 3'b111;
        default: decode_ppm = 3'b000;
      endcase
    end
  endfunction

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      r_in   <= 1'b1;
      r_in_d <= 1'b1;
    end else begin
      r_in   <= ir_rx_in;
      r_in_d <= r_in;
    end
  end

  assign rx_pulse_active = ~r_in;
  assign rx_rise_edge    = r_in_d & ~r_in;
  assign dec_res         = decode_ppm(sym_capture);
  assign sym_valid       = dec_res[2];
  assign sym_val         = dec_res[1:0];
  assign byte_assembled  = {sym_val, shift_reg[5:0]};

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      state           <= S_IDLE;
      ticks           <= '0;
      chip_idx        <= '0;
      sym_capture     <= '0;
      shift_reg       <= '0;
      pair_cnt        <= '0;
      preamble_cnt    <= '0;
      silence_sym_cnt <= '0;
      byte_cnt        <= '0;
      flush_ptr       <= '0;
      check_ptr       <= '0;
      crc_running     <= 32'hFFFF_FFFF;
      payload_len     <= '0;
      m_axis_tdata    <= 8'h00;
      m_axis_tvalid   <= 1'b0;
      m_axis_tlast    <= 1'b0;
      rx_active       <= 1'b0;
      crc_error       <= 1'b0;
      overrun_error   <= 1'b0;
    end else if (!enable) begin
      state         <= S_IDLE;
      ticks         <= '0;
      chip_idx      <= '0;
      sym_capture   <= '0;
      m_axis_tvalid <= 1'b0;
      m_axis_tlast  <= 1'b0;
      rx_active     <= 1'b0;
    end else begin
      if ((state == S_PREAMBLE) || (state == S_DATA)) begin
        if (rx_rise_edge && ((ticks > CNT_CHIP_MAX[TICK_W-1:0]-2) || (ticks < 2))) ticks <= '0;
        else if (ticks == CNT_CHIP_MAX[TICK_W-1:0]) ticks <= '0;
        else ticks <= ticks + 1'b1;
      end

      case (state)
        S_IDLE: begin
          rx_active       <= 1'b0;
          m_axis_tvalid   <= 1'b0;
          m_axis_tlast    <= 1'b0;
          if (rx_rise_edge) begin
            state           <= S_PREAMBLE;
            ticks           <= '0;
            chip_idx        <= '0;
            sym_capture     <= '0;
            shift_reg       <= '0;
            pair_cnt        <= '0;
            preamble_cnt    <= '0;
            silence_sym_cnt <= '0;
            byte_cnt        <= '0;
            flush_ptr       <= '0;
            check_ptr       <= '0;
            crc_error       <= 1'b0;
            overrun_error   <= 1'b0;
            rx_active       <= 1'b1;
          end
        end

        S_PREAMBLE: begin
          if (ticks == TICK_W'(4) && rx_pulse_active) sym_capture[3 - chip_idx] <= 1'b1;
          if (ticks == CNT_CHIP_MAX[TICK_W-1:0]) begin
            if (chip_idx == 2'd3) begin
              chip_idx <= 2'd0;
              if (sym_valid) begin
                preamble_cnt    <= preamble_cnt + 1'b1;
                silence_sym_cnt <= 8'd0;
              end else begin
                silence_sym_cnt <= silence_sym_cnt + 1'b1;
              end
              sym_capture <= '0;
              if ((preamble_cnt >= PREAMBLE_SYMS-1) && sym_valid) begin
                state           <= S_DATA;
                shift_reg       <= '0;
                pair_cnt        <= '0;
                byte_cnt        <= '0;
                silence_sym_cnt <= '0;
              end else if (silence_sym_cnt >= EOF_SILENCE_SYMS + 4) begin
                state     <= S_IDLE;
                rx_active <= 1'b0;
              end
            end else begin
              chip_idx <= chip_idx + 1'b1;
            end
          end
        end

        S_DATA: begin
          if (ticks == TICK_W'(4) && rx_pulse_active) sym_capture[3 - chip_idx] <= 1'b1;
          if (ticks == CNT_CHIP_MAX[TICK_W-1:0]) begin
            if (chip_idx == 2'd3) begin
              chip_idx <= 2'd0;
              if (sym_valid) begin
                silence_sym_cnt <= 8'd0;
                case (pair_cnt)
                  2'd0: shift_reg[1:0] <= sym_val;
                  2'd1: shift_reg[3:2] <= sym_val;
                  2'd2: shift_reg[5:4] <= sym_val;
                  default: ;
                endcase
                if (pair_cnt == 2'd3) begin
                  pair_cnt <= 2'd0;
                  if (byte_cnt < BUF_BYTES) begin
                    rx_buf[byte_cnt] <= byte_assembled;
                    byte_cnt         <= byte_cnt + 1'b1;
                  end else begin
                    overrun_error <= 1'b1;
                    state         <= S_IDLE;
                    rx_active     <= 1'b0;
                  end
                end else begin
                  pair_cnt <= pair_cnt + 1'b1;
                end
              end else begin
                silence_sym_cnt <= silence_sym_cnt + 1'b1;
                if ((silence_sym_cnt >= EOF_SILENCE_SYMS-1) && (pair_cnt == 2'd0) && (byte_cnt >= 4)) begin
                  state       <= S_CHECK;
                  check_ptr   <= '0;
                  crc_running <= 32'hFFFF_FFFF;
                  payload_len <= byte_cnt - 4;
                end else if (silence_sym_cnt >= EOF_SILENCE_SYMS + 8) begin
                  state     <= S_IDLE;
                  rx_active <= 1'b0;
                end
              end
              sym_capture <= '0;
            end else begin
              chip_idx <= chip_idx + 1'b1;
            end
          end
        end

        S_CHECK: begin
          if (check_ptr < payload_len) begin
            crc_running <= crc32_next_byte(rx_buf[check_ptr], crc_running);
            check_ptr   <= check_ptr + 1'b1;
          end else begin
            if ((~crc_running[7:0]   == rx_buf[payload_len + 0]) &&
                (~crc_running[15:8]  == rx_buf[payload_len + 1]) &&
                (~crc_running[23:16] == rx_buf[payload_len + 2]) &&
                (~crc_running[31:24] == rx_buf[payload_len + 3])) begin
              state       <= S_FLUSH;
              flush_ptr   <= '0;
              m_axis_tvalid <= 1'b0;
            end else begin
              crc_error <= 1'b1;
              state     <= S_IDLE;
              rx_active <= 1'b0;
            end
          end
        end

        S_FLUSH: begin
          if (!m_axis_tvalid || m_axis_tready) begin
            if (flush_ptr < payload_len) begin
              m_axis_tdata  <= rx_buf[flush_ptr];
              m_axis_tvalid <= 1'b1;
              m_axis_tlast  <= (flush_ptr == payload_len - 1'b1);
              flush_ptr     <= flush_ptr + 1'b1;
            end else begin
              m_axis_tvalid <= 1'b0;
              m_axis_tlast  <= 1'b0;
              state         <= S_IDLE;
              rx_active     <= 1'b0;
            end
          end
        end

        default: begin
          state     <= S_IDLE;
          rx_active <= 1'b0;
        end
      endcase
    end
  end
endmodule
