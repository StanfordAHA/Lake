from kratos import *
from lake.modules.passthru import *
from lake.modules.register_file import RegisterFile
from lake.attributes.config_reg_attr import ConfigRegAttr
from lake.attributes.range_group import RangeGroupAttr
from lake.passes.passes import lift_config_reg
from lake.modules.sram_stub import SRAMStub
from lake.modules.for_loop import ForLoop
from lake.modules.addr_gen import AddrGen
from lake.modules.spec.sched_gen import SchedGen
from lake.utils.util import safe_wire, add_counter, decode
import kratos as kts


class StrgUBSRAMTBShared(Generator):
    def __init__(self,
                 data_width=16,  # CGRA Params
                 mem_width=64,
                 mem_depth=512,
                 banks=1,
                 input_addr_iterator_support=6,
                 output_addr_iterator_support=6,
                 input_sched_iterator_support=6,
                 output_sched_iterator_support=6,
                 config_width=16,
                 #  output_config_width=16,
                 interconnect_input_ports=2,  # Connection to int
                 interconnect_output_ports=2,
                 mem_input_ports=1,
                 mem_output_ports=1,
                 read_delay=1,  # Cycle delay in read (SRAM vs Register File)
                 rw_same_cycle=False,  # Does the memory allow r+w in same cycle?
                 agg_height=4,
                 tb_height=2):

        super().__init__("strg_ub_sram_tb_shared")

        ##################################################################################
        # Capture constructor parameter...
        ##################################################################################
        self.fetch_width = mem_width // data_width
        self.interconnect_input_ports = interconnect_input_ports
        self.interconnect_output_ports = interconnect_output_ports
        self.agg_height = agg_height
        self.tb_height = tb_height
        self.mem_depth = mem_depth
        self.config_width = config_width
        self.data_width = data_width
        self.input_addr_iterator_support = input_addr_iterator_support
        self.input_sched_iterator_support = input_sched_iterator_support

        self.default_iterator_support = 6
        self.default_config_width = 16
        self.sram_iterator_support = 6
        self.agg_rd_addr_gen_width = 8

        ##################################################################################
        # IO
        ##################################################################################
        self._clk = self.clock("clk")
        self._rst_n = self.reset("rst_n")

        self._cycle_count = self.input("cycle_count", 16)

        self._loops_sram2tb_mux_sel = self.output("loops_sram2tb_mux_sel", 
                              width=max(clog2(self.default_iterator_support), 1),
                              size=self.interconnect_output_ports)

        self._loops_sram2tb_restart = self.output("loops_sram2tb_restart", 
                              width=1,
                              size=self.interconnect_output_ports)

        self._t_read_out = self.output("t_read_out", self.interconnect_output_ports)
        self._t_read = self.var("t_read", self.interconnect_output_ports)
        self.wire(self._t_read_out, self._t_read)

        self._mux_sel_d1 = self.output("mux_sel_d1", kts.clog2(self.default_iterator_support), size=self.interconnect_output_ports,
                                    packed=True,
                                    explicit_array=True)
        
        self._t_read_d1 = self.output("t_read_d1", self.interconnect_output_ports)
        self._restart_d1 = self.output("restart_d1", self.interconnect_output_ports)

        ##################################################################################
        # TB PATHS
        ##################################################################################
        for i in range(self.interconnect_output_ports):

            loops_sram2tb = ForLoop(iterator_support=self.default_iterator_support,
                                    config_width=self.default_config_width)

            self.add_child(f"loops_buf2out_autovec_read_{i}",
                           loops_sram2tb,
                           clk=self._clk,
                           rst_n=self._rst_n,
                           step=self._t_read[i])

            self.wire(self._loops_sram2tb_mux_sel[i], loops_sram2tb.ports.mux_sel_out)
            self.wire(self._loops_sram2tb_restart[i], loops_sram2tb.ports.restart)

            self.add_child(f"output_sched_gen_{i}",
                           SchedGen(iterator_support=self.default_iterator_support,
                                    # config_width=self.default_config_width),
                                    config_width=16),
                           clk=self._clk,
                           rst_n=self._rst_n,
                           cycle_count=self._cycle_count,
                           mux_sel=loops_sram2tb.ports.mux_sel_out,
                           finished=loops_sram2tb.ports.restart,
                           valid_output=self._t_read[i])


            @always_ff((posedge, "clk"), (negedge, "rst_n"))
            def delay_read():
                if ~self._rst_n:
                    self._t_read_d1[i] = 0
                    self._mux_sel_d1[i] = 0
                    self._restart_d1[i] = 0
                else:
                    self._t_read_d1[i] = self._t_read[i]
                    self._mux_sel_d1[i] = loops_sram2tb.ports.mux_sel_out
                    self._restart_d1[i] = loops_sram2tb.ports.restart
            self.add_code(delay_read)


if __name__ == "__main__":
    lake_dut = StrgUBSRAMTBShared()
    verilog(lake_dut, filename="strg_ub_sram_tb_shared.sv",
            optimize_if=False,
            additional_passes={"lift config regs": lift_config_reg})