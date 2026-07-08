# Definitional proc to organize widgets for parameters.
proc init_gui { IPINST } {
  ipgui::add_param $IPINST -name "Component_Name"
  #Adding Page
  ipgui::add_page $IPINST -name "Page 0"


}

proc update_PARAM_VALUE.CNT_CHIP_MAX { PARAM_VALUE.CNT_CHIP_MAX } {
	# Procedure called to update CNT_CHIP_MAX when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CNT_CHIP_MAX { PARAM_VALUE.CNT_CHIP_MAX } {
	# Procedure called to validate CNT_CHIP_MAX
	return true
}

proc update_PARAM_VALUE.CNT_PREAMBLE { PARAM_VALUE.CNT_PREAMBLE } {
	# Procedure called to update CNT_PREAMBLE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CNT_PREAMBLE { PARAM_VALUE.CNT_PREAMBLE } {
	# Procedure called to validate CNT_PREAMBLE
	return true
}

proc update_PARAM_VALUE.C_S_AXI_ADDR_WIDTH { PARAM_VALUE.C_S_AXI_ADDR_WIDTH } {
	# Procedure called to update C_S_AXI_ADDR_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_S_AXI_ADDR_WIDTH { PARAM_VALUE.C_S_AXI_ADDR_WIDTH } {
	# Procedure called to validate C_S_AXI_ADDR_WIDTH
	return true
}

proc update_PARAM_VALUE.C_S_AXI_DATA_WIDTH { PARAM_VALUE.C_S_AXI_DATA_WIDTH } {
	# Procedure called to update C_S_AXI_DATA_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_S_AXI_DATA_WIDTH { PARAM_VALUE.C_S_AXI_DATA_WIDTH } {
	# Procedure called to validate C_S_AXI_DATA_WIDTH
	return true
}

proc update_PARAM_VALUE.EOF_SILENCE_SYMS { PARAM_VALUE.EOF_SILENCE_SYMS } {
	# Procedure called to update EOF_SILENCE_SYMS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.EOF_SILENCE_SYMS { PARAM_VALUE.EOF_SILENCE_SYMS } {
	# Procedure called to validate EOF_SILENCE_SYMS
	return true
}

proc update_PARAM_VALUE.FRAGMENT_BYTES { PARAM_VALUE.FRAGMENT_BYTES } {
	# Procedure called to update FRAGMENT_BYTES when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.FRAGMENT_BYTES { PARAM_VALUE.FRAGMENT_BYTES } {
	# Procedure called to validate FRAGMENT_BYTES
	return true
}

proc update_PARAM_VALUE.FRAG_TIMEOUT_CYCLES { PARAM_VALUE.FRAG_TIMEOUT_CYCLES } {
	# Procedure called to update FRAG_TIMEOUT_CYCLES when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.FRAG_TIMEOUT_CYCLES { PARAM_VALUE.FRAG_TIMEOUT_CYCLES } {
	# Procedure called to validate FRAG_TIMEOUT_CYCLES
	return true
}

proc update_PARAM_VALUE.LANE_COUNT { PARAM_VALUE.LANE_COUNT } {
	# Procedure called to update LANE_COUNT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.LANE_COUNT { PARAM_VALUE.LANE_COUNT } {
	# Procedure called to validate LANE_COUNT
	return true
}

proc update_PARAM_VALUE.MAX_FRAGS { PARAM_VALUE.MAX_FRAGS } {
	# Procedure called to update MAX_FRAGS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.MAX_FRAGS { PARAM_VALUE.MAX_FRAGS } {
	# Procedure called to validate MAX_FRAGS
	return true
}

proc update_PARAM_VALUE.MAX_FRAME_BYTES { PARAM_VALUE.MAX_FRAME_BYTES } {
	# Procedure called to update MAX_FRAME_BYTES when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.MAX_FRAME_BYTES { PARAM_VALUE.MAX_FRAME_BYTES } {
	# Procedure called to validate MAX_FRAME_BYTES
	return true
}

proc update_PARAM_VALUE.MAX_PACKET_BYTES { PARAM_VALUE.MAX_PACKET_BYTES } {
	# Procedure called to update MAX_PACKET_BYTES when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.MAX_PACKET_BYTES { PARAM_VALUE.MAX_PACKET_BYTES } {
	# Procedure called to validate MAX_PACKET_BYTES
	return true
}

proc update_PARAM_VALUE.MAX_RETRY { PARAM_VALUE.MAX_RETRY } {
	# Procedure called to update MAX_RETRY when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.MAX_RETRY { PARAM_VALUE.MAX_RETRY } {
	# Procedure called to validate MAX_RETRY
	return true
}

proc update_PARAM_VALUE.PARALLEL_2LANE_MODE { PARAM_VALUE.PARALLEL_2LANE_MODE } {
	# Procedure called to update PARALLEL_2LANE_MODE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.PARALLEL_2LANE_MODE { PARAM_VALUE.PARALLEL_2LANE_MODE } {
	# Procedure called to validate PARALLEL_2LANE_MODE
	return true
}

proc update_PARAM_VALUE.REASSEMBLY_TIMEOUT_CYCLES { PARAM_VALUE.REASSEMBLY_TIMEOUT_CYCLES } {
	# Procedure called to update REASSEMBLY_TIMEOUT_CYCLES when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.REASSEMBLY_TIMEOUT_CYCLES { PARAM_VALUE.REASSEMBLY_TIMEOUT_CYCLES } {
	# Procedure called to validate REASSEMBLY_TIMEOUT_CYCLES
	return true
}

proc update_PARAM_VALUE.RX_ASYNC_FIFO_DEPTH { PARAM_VALUE.RX_ASYNC_FIFO_DEPTH } {
	# Procedure called to update RX_ASYNC_FIFO_DEPTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RX_ASYNC_FIFO_DEPTH { PARAM_VALUE.RX_ASYNC_FIFO_DEPTH } {
	# Procedure called to validate RX_ASYNC_FIFO_DEPTH
	return true
}

proc update_PARAM_VALUE.RX_DATA_PHASE_DELAY_CYCLES { PARAM_VALUE.RX_DATA_PHASE_DELAY_CYCLES } {
	# Procedure called to update RX_DATA_PHASE_DELAY_CYCLES when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RX_DATA_PHASE_DELAY_CYCLES { PARAM_VALUE.RX_DATA_PHASE_DELAY_CYCLES } {
	# Procedure called to validate RX_DATA_PHASE_DELAY_CYCLES
	return true
}

proc update_PARAM_VALUE.RX_PREAMBLE_REALIGN_EDGE { PARAM_VALUE.RX_PREAMBLE_REALIGN_EDGE } {
	# Procedure called to update RX_PREAMBLE_REALIGN_EDGE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RX_PREAMBLE_REALIGN_EDGE { PARAM_VALUE.RX_PREAMBLE_REALIGN_EDGE } {
	# Procedure called to validate RX_PREAMBLE_REALIGN_EDGE
	return true
}

proc update_PARAM_VALUE.RX_SELF_BLANK_CYCLES { PARAM_VALUE.RX_SELF_BLANK_CYCLES } {
	# Procedure called to update RX_SELF_BLANK_CYCLES when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RX_SELF_BLANK_CYCLES { PARAM_VALUE.RX_SELF_BLANK_CYCLES } {
	# Procedure called to validate RX_SELF_BLANK_CYCLES
	return true
}

proc update_PARAM_VALUE.RX_TO_TX_GUARD_CYCLES { PARAM_VALUE.RX_TO_TX_GUARD_CYCLES } {
	# Procedure called to update RX_TO_TX_GUARD_CYCLES when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RX_TO_TX_GUARD_CYCLES { PARAM_VALUE.RX_TO_TX_GUARD_CYCLES } {
	# Procedure called to validate RX_TO_TX_GUARD_CYCLES
	return true
}

proc update_PARAM_VALUE.STREAM_FULL_MODE { PARAM_VALUE.STREAM_FULL_MODE } {
	# Procedure called to update STREAM_FULL_MODE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.STREAM_FULL_MODE { PARAM_VALUE.STREAM_FULL_MODE } {
	# Procedure called to validate STREAM_FULL_MODE
	return true
}

proc update_PARAM_VALUE.STREAM_NODE_ID { PARAM_VALUE.STREAM_NODE_ID } {
	# Procedure called to update STREAM_NODE_ID when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.STREAM_NODE_ID { PARAM_VALUE.STREAM_NODE_ID } {
	# Procedure called to validate STREAM_NODE_ID
	return true
}

proc update_PARAM_VALUE.TX_ASYNC_FIFO_DEPTH { PARAM_VALUE.TX_ASYNC_FIFO_DEPTH } {
	# Procedure called to update TX_ASYNC_FIFO_DEPTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.TX_ASYNC_FIFO_DEPTH { PARAM_VALUE.TX_ASYNC_FIFO_DEPTH } {
	# Procedure called to validate TX_ASYNC_FIFO_DEPTH
	return true
}

proc update_PARAM_VALUE.TX_ONLY_ACK_MODE { PARAM_VALUE.TX_ONLY_ACK_MODE } {
	# Procedure called to update TX_ONLY_ACK_MODE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.TX_ONLY_ACK_MODE { PARAM_VALUE.TX_ONLY_ACK_MODE } {
	# Procedure called to validate TX_ONLY_ACK_MODE
	return true
}

proc update_PARAM_VALUE.TX_POST_ACK_GUARD_CYCLES { PARAM_VALUE.TX_POST_ACK_GUARD_CYCLES } {
	# Procedure called to update TX_POST_ACK_GUARD_CYCLES when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.TX_POST_ACK_GUARD_CYCLES { PARAM_VALUE.TX_POST_ACK_GUARD_CYCLES } {
	# Procedure called to validate TX_POST_ACK_GUARD_CYCLES
	return true
}


proc update_MODELPARAM_VALUE.LANE_COUNT { MODELPARAM_VALUE.LANE_COUNT PARAM_VALUE.LANE_COUNT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.LANE_COUNT}] ${MODELPARAM_VALUE.LANE_COUNT}
}

proc update_MODELPARAM_VALUE.MAX_PACKET_BYTES { MODELPARAM_VALUE.MAX_PACKET_BYTES PARAM_VALUE.MAX_PACKET_BYTES } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.MAX_PACKET_BYTES}] ${MODELPARAM_VALUE.MAX_PACKET_BYTES}
}

proc update_MODELPARAM_VALUE.FRAGMENT_BYTES { MODELPARAM_VALUE.FRAGMENT_BYTES PARAM_VALUE.FRAGMENT_BYTES } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.FRAGMENT_BYTES}] ${MODELPARAM_VALUE.FRAGMENT_BYTES}
}

proc update_MODELPARAM_VALUE.MAX_RETRY { MODELPARAM_VALUE.MAX_RETRY PARAM_VALUE.MAX_RETRY } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.MAX_RETRY}] ${MODELPARAM_VALUE.MAX_RETRY}
}

proc update_MODELPARAM_VALUE.CNT_CHIP_MAX { MODELPARAM_VALUE.CNT_CHIP_MAX PARAM_VALUE.CNT_CHIP_MAX } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CNT_CHIP_MAX}] ${MODELPARAM_VALUE.CNT_CHIP_MAX}
}

proc update_MODELPARAM_VALUE.CNT_PREAMBLE { MODELPARAM_VALUE.CNT_PREAMBLE PARAM_VALUE.CNT_PREAMBLE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CNT_PREAMBLE}] ${MODELPARAM_VALUE.CNT_PREAMBLE}
}

proc update_MODELPARAM_VALUE.EOF_SILENCE_SYMS { MODELPARAM_VALUE.EOF_SILENCE_SYMS PARAM_VALUE.EOF_SILENCE_SYMS } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.EOF_SILENCE_SYMS}] ${MODELPARAM_VALUE.EOF_SILENCE_SYMS}
}

proc update_MODELPARAM_VALUE.FRAG_TIMEOUT_CYCLES { MODELPARAM_VALUE.FRAG_TIMEOUT_CYCLES PARAM_VALUE.FRAG_TIMEOUT_CYCLES } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.FRAG_TIMEOUT_CYCLES}] ${MODELPARAM_VALUE.FRAG_TIMEOUT_CYCLES}
}

proc update_MODELPARAM_VALUE.REASSEMBLY_TIMEOUT_CYCLES { MODELPARAM_VALUE.REASSEMBLY_TIMEOUT_CYCLES PARAM_VALUE.REASSEMBLY_TIMEOUT_CYCLES } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.REASSEMBLY_TIMEOUT_CYCLES}] ${MODELPARAM_VALUE.REASSEMBLY_TIMEOUT_CYCLES}
}

proc update_MODELPARAM_VALUE.MAX_FRAGS { MODELPARAM_VALUE.MAX_FRAGS PARAM_VALUE.MAX_FRAGS } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.MAX_FRAGS}] ${MODELPARAM_VALUE.MAX_FRAGS}
}

proc update_MODELPARAM_VALUE.MAX_FRAME_BYTES { MODELPARAM_VALUE.MAX_FRAME_BYTES PARAM_VALUE.MAX_FRAME_BYTES } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.MAX_FRAME_BYTES}] ${MODELPARAM_VALUE.MAX_FRAME_BYTES}
}

proc update_MODELPARAM_VALUE.C_S_AXI_DATA_WIDTH { MODELPARAM_VALUE.C_S_AXI_DATA_WIDTH PARAM_VALUE.C_S_AXI_DATA_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_S_AXI_DATA_WIDTH}] ${MODELPARAM_VALUE.C_S_AXI_DATA_WIDTH}
}

proc update_MODELPARAM_VALUE.C_S_AXI_ADDR_WIDTH { MODELPARAM_VALUE.C_S_AXI_ADDR_WIDTH PARAM_VALUE.C_S_AXI_ADDR_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_S_AXI_ADDR_WIDTH}] ${MODELPARAM_VALUE.C_S_AXI_ADDR_WIDTH}
}

proc update_MODELPARAM_VALUE.TX_ASYNC_FIFO_DEPTH { MODELPARAM_VALUE.TX_ASYNC_FIFO_DEPTH PARAM_VALUE.TX_ASYNC_FIFO_DEPTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.TX_ASYNC_FIFO_DEPTH}] ${MODELPARAM_VALUE.TX_ASYNC_FIFO_DEPTH}
}

proc update_MODELPARAM_VALUE.RX_ASYNC_FIFO_DEPTH { MODELPARAM_VALUE.RX_ASYNC_FIFO_DEPTH PARAM_VALUE.RX_ASYNC_FIFO_DEPTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RX_ASYNC_FIFO_DEPTH}] ${MODELPARAM_VALUE.RX_ASYNC_FIFO_DEPTH}
}

proc update_MODELPARAM_VALUE.RX_TO_TX_GUARD_CYCLES { MODELPARAM_VALUE.RX_TO_TX_GUARD_CYCLES PARAM_VALUE.RX_TO_TX_GUARD_CYCLES } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RX_TO_TX_GUARD_CYCLES}] ${MODELPARAM_VALUE.RX_TO_TX_GUARD_CYCLES}
}

proc update_MODELPARAM_VALUE.TX_POST_ACK_GUARD_CYCLES { MODELPARAM_VALUE.TX_POST_ACK_GUARD_CYCLES PARAM_VALUE.TX_POST_ACK_GUARD_CYCLES } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.TX_POST_ACK_GUARD_CYCLES}] ${MODELPARAM_VALUE.TX_POST_ACK_GUARD_CYCLES}
}

proc update_MODELPARAM_VALUE.TX_ONLY_ACK_MODE { MODELPARAM_VALUE.TX_ONLY_ACK_MODE PARAM_VALUE.TX_ONLY_ACK_MODE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.TX_ONLY_ACK_MODE}] ${MODELPARAM_VALUE.TX_ONLY_ACK_MODE}
}

proc update_MODELPARAM_VALUE.STREAM_FULL_MODE { MODELPARAM_VALUE.STREAM_FULL_MODE PARAM_VALUE.STREAM_FULL_MODE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.STREAM_FULL_MODE}] ${MODELPARAM_VALUE.STREAM_FULL_MODE}
}

proc update_MODELPARAM_VALUE.STREAM_NODE_ID { MODELPARAM_VALUE.STREAM_NODE_ID PARAM_VALUE.STREAM_NODE_ID } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.STREAM_NODE_ID}] ${MODELPARAM_VALUE.STREAM_NODE_ID}
}

proc update_MODELPARAM_VALUE.RX_PREAMBLE_REALIGN_EDGE { MODELPARAM_VALUE.RX_PREAMBLE_REALIGN_EDGE PARAM_VALUE.RX_PREAMBLE_REALIGN_EDGE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RX_PREAMBLE_REALIGN_EDGE}] ${MODELPARAM_VALUE.RX_PREAMBLE_REALIGN_EDGE}
}

proc update_MODELPARAM_VALUE.RX_DATA_PHASE_DELAY_CYCLES { MODELPARAM_VALUE.RX_DATA_PHASE_DELAY_CYCLES PARAM_VALUE.RX_DATA_PHASE_DELAY_CYCLES } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RX_DATA_PHASE_DELAY_CYCLES}] ${MODELPARAM_VALUE.RX_DATA_PHASE_DELAY_CYCLES}
}

proc update_MODELPARAM_VALUE.PARALLEL_2LANE_MODE { MODELPARAM_VALUE.PARALLEL_2LANE_MODE PARAM_VALUE.PARALLEL_2LANE_MODE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.PARALLEL_2LANE_MODE}] ${MODELPARAM_VALUE.PARALLEL_2LANE_MODE}
}

proc update_MODELPARAM_VALUE.RX_SELF_BLANK_CYCLES { MODELPARAM_VALUE.RX_SELF_BLANK_CYCLES PARAM_VALUE.RX_SELF_BLANK_CYCLES } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RX_SELF_BLANK_CYCLES}] ${MODELPARAM_VALUE.RX_SELF_BLANK_CYCLES}
}

