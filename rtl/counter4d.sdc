create_clock -name clk -period 10.0 [get_ports clk]
set_input_delay -clock clk 2.0 [get_ports rst_n]
set_input_delay -clock clk 2.0 [get_ports en]
set_output_delay -clock clk 2.0 [get_ports {count[0] count[1] count[2] count[3]}]
