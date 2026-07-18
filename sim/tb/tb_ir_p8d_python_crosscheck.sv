`timescale 1ns/1ps
module tb_ir_p8d_python_crosscheck;
  logic [15:0] ack_base,query_sequence;
  logic [63:0] bitmap;
  logic [6:0] bitmap_width;
  logic cumulative,selective,acked,malformed;
  ir_sack_codec #(.SACK_BITS(64)) codec (
    .ack_base_i(ack_base),.sack_bitmap_i(bitmap),.bitmap_width_i(bitmap_width),
    .query_sequence_i(query_sequence),.query_cumulative_acked_o(cumulative),
    .query_sack_acked_o(selective),.query_acked_o(acked),.malformed_o(malformed)
  );
  initial begin
    bitmap_width=7'd64;
    for(int record_index=0;record_index<2048;record_index++) begin
      integer distance;
      integer lane;
      integer attempt_count;
      integer occupancy;
      integer descriptor_completion;
      integer error_reason;
      integer path_epoch;
      query_sequence=(16'hfff0+record_index)&16'hffff;
      distance=record_index%4;
      ack_base=query_sequence-distance;
      bitmap=64'd1<<distance;
      lane=(record_index*5+(record_index>>3))&7;
      attempt_count=1+record_index%8;
      occupancy=record_index%65;
      descriptor_completion=(record_index%3)?1:0;
      error_reason=(record_index%17)?0:4;
      path_epoch=7+record_index/256;
      #1;
      if(malformed||!acked||!selective)
        $fatal(1,"P8D_CROSSCHECK_CODEC_FAIL record=%0d",record_index);
      $display("P8D_XCHECK,%0d,%08x,%04x,%0d,%0d,%0d,%04x,%016x,%0d,%0d,%0d",
        record_index,32'h10203040,query_sequence,path_epoch,lane,attempt_count,
        ack_base,bitmap,occupancy,descriptor_completion,error_reason);
    end
    $display("P8D_RTL_PYTHON_CROSSCHECK_RECORDS=2048");
    $display("TB_IR_P8D_PYTHON_CROSSCHECK_PASS=1");
    $finish;
  end
endmodule
