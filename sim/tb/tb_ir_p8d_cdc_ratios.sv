`timescale 1ns/1ps
module p8d_cdc_case #(
  parameter int CASE_ID=0,parameter int SRC_HALF_NS=5,parameter int DST_HALF_NS=5
) (output logic done_o);
  logic src_clk=0,dst_clk=0,rst_n=0,src_valid,src_ready,dst_valid,dst_ready;
  logic [63:0] src_data,dst_data;
  logic [31:0] lfsr;
  integer received;
  always #(SRC_HALF_NS) src_clk=~src_clk;
  always #(DST_HALF_NS) dst_clk=~dst_clk;
  ir_p8d_async_descriptor_bridge bridge(
    .src_clk,.src_rst_n(rst_n),.src_valid_i(src_valid),.src_ready_o(src_ready),
    .src_data_i(src_data),.dst_clk,.dst_rst_n(rst_n),.dst_valid_o(dst_valid),
    .dst_ready_i(dst_ready),.dst_data_o(dst_data)
  );
  always @(negedge dst_clk) begin
    if(!rst_n)begin lfsr<=32'h13579bdf^CASE_ID;dst_ready<=0;end
    else begin
      lfsr<={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      dst_ready<=lfsr[0]|lfsr[4];
    end
  end
  always @(posedge dst_clk) begin
    if(!rst_n)received=0;
    else if(dst_valid&&dst_ready)begin
      if(dst_data!=={CASE_ID[31:0],received[31:0]})
        $fatal(1,"P8D_CDC_CASE_%0d_DATA_FAIL got=%h expected_index=%0d",CASE_ID,dst_data,received);
      received=received+1;
      if(received==128)done_o=1;
    end
  end
  initial begin
    done_o=0;src_valid=0;src_data=0;dst_ready=0;lfsr=32'h1;
    #37;rst_n=1;
    for(int item=0;item<128;item++)begin
      @(negedge src_clk);src_data={CASE_ID[31:0],item[31:0]};src_valid=1;
      while(!src_ready)@(negedge src_clk);
      @(posedge src_clk);#1;src_valid=0;
    end
  end
endmodule

module tb_ir_p8d_cdc_ratios;
  logic [3:0] done;
  p8d_cdc_case #(.CASE_ID(0),.SRC_HALF_NS(5),.DST_HALF_NS(5)) ratio_1_1(.done_o(done[0]));
  p8d_cdc_case #(.CASE_ID(1),.SRC_HALF_NS(10),.DST_HALF_NS(5)) ratio_2_1(.done_o(done[1]));
  p8d_cdc_case #(.CASE_ID(2),.SRC_HALF_NS(6),.DST_HALF_NS(4)) ratio_3_2(.done_o(done[2]));
  p8d_cdc_case #(.CASE_ID(3),.SRC_HALF_NS(7),.DST_HALF_NS(11)) ratio_async(.done_o(done[3]));
  initial begin
    wait(&done);#50;
    $display("P8D_CDC_RATIO_1_1_PASS=1");
    $display("P8D_CDC_RATIO_2_1_PASS=1");
    $display("P8D_CDC_RATIO_3_2_PASS=1");
    $display("P8D_CDC_ASYNC_PHASE_PASS=1");
    $display("TB_IR_P8D_CDC_RATIOS_PASS=1");
    $finish;
  end
  initial begin #200000;$fatal(1,"P8D_CDC_TIMEOUT");end
endmodule
