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
import kratos as kts


class StrgUB(Generator):
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
                 agg_height=4):
        super().__init__("strg_ub", debug=True)

        self.fetch_width = mem_width // data_width
        self.interconnect_input_ports = interconnect_input_ports
        self.interconnect_output_ports = interconnect_output_ports
        self.agg_height = agg_height
        self.mem_depth = mem_depth
        # generation parameters
        # inputs
        self._clk = self.clock("clk")
        self._rst_n = self.reset("rst_n")

        self._data_in = self.input("data_in", data_width,
                                   size=self.interconnect_input_ports,
                                   packed=True,
                                   explicit_array=True)

        # Create cycle counter to share...
        self._cycle_count = self.var("cycle_count", 16)
        self.add_code(self.increment_cycle_count)

        # outputs
        self._data_out = self.output("data_out", data_width,
                                     size=self.interconnect_output_ports,
                                     packed=True,
                                     explicit_array=True)

        # local variables
        self._write = self.var("write", 1)
        self._read = self.var("read", 1)
        self._read_d1 = self.var("read_d1", 1)
        self.add_code(self.delay_read)

        self._write_addr = self.var("write_addr", config_width)
        self._read_addr = self.var("read_addr", config_width)
        self._addr = self.var("addr", clog2(mem_depth))

        self._sram_write_data = self.var("sram_write_data", data_width,
                                         size=self.fetch_width,
                                         packed=True)
        self._sram_read_data = self.var("sram_read_data", data_width,
                                        size=self.fetch_width,
                                        packed=True,
                                        explicit_array=True)

        self._data_to_sram = self.output("data_to_strg", data_width,
                                         size=self.fetch_width,
                                         packed=True)
        self._data_from_sram = self.input("data_from_strg", data_width,
                                          size=self.fetch_width,
                                          packed=True)

        self._addr_to_sram = self.output("addr_out", clog2(mem_depth), packed=True)

        self.wire(self._addr_to_sram, self._addr)
        self.wire(self._data_to_sram, self._sram_write_data)
        self.wire(self._data_from_sram, self._sram_read_data)
        self.wire(self._wen_to_sram, self._write)
        self.wire(self._cen_to_sram, self._write | self._read)

        self._agg_write_index = self.var("agg_write_index", 2, size=4)

        self._output_port_sel_addr = self.var("output_port_sel_addr",
                                              max(1, clog2(self.interconnect_output_ports)))

        # -------------------------------- Delineate new group -------------------------------
        fl_ctr_sram_rd = ForLoop(iterator_support=6,
                                 config_width=16)
        loop_itr = fl_ctr_sram_rd.get_iter()
        loop_wth = fl_ctr_sram_rd.get_cfg_width()

        self.add_child(f"loops_buf2out_autovec_read",
                       fl_ctr_sram_rd,
                       clk=self._clk,
                       rst_n=self._rst_n,
                       step=self._read)

        self.add_child(f"output_addr_gen",
                       AddrGen(iterator_support=6,
                               config_width=16),
                       clk=self._clk,
                       rst_n=self._rst_n,
                       step=self._read,
                       mux_sel=fl_ctr_sram_rd.ports.mux_sel_out,
                       addr_out=self._read_addr)

        self.add_child(f"output_sched_gen",
                       SchedGen(iterator_support=6,
                                config_width=16),
                       clk=self._clk,
                       rst_n=self._rst_n,
                       cycle_count=self._cycle_count,
                       mux_sel=fl_ctr_sram_rd.ports.mux_sel_out,
                       valid_output=self._read)

        self._tb_read = self.var("tb_read", self.interconnect_output_ports)
        self.tb_height = 4

        self._tb_write_addr = self.var("tb_write_addr", 6,
                                       size=self.interconnect_output_ports,
                                       packed=True,
                                       explicit_array=True)
        self._tb_read_addr = self.var("tb_read_addr", 6,
                                      size=self.interconnect_output_ports,
                                      packed=True,
                                      explicit_array=True)

        self._tb = self.var("tb",
                            width=data_width,
                            size=(self.interconnect_output_ports,
                                  self.tb_height,
                                  self.fetch_width),
                            packed=True,
                            explicit_array=True)

        for i in range(self.interconnect_output_ports):
            fl_ctr_tb_wr = ForLoop(iterator_support=2,
                                   config_width=6)
            loop_itr = fl_ctr_tb_wr.get_iter()
            loop_wth = fl_ctr_tb_wr.get_cfg_width()

            self.add_child(f"loops_buf2out_autovec_write_{i}",
                           fl_ctr_tb_wr,
                           clk=self._clk,
                           rst_n=self._rst_n,
                           step=self._read_d1 & (self._output_port_sel_addr ==
                                                 const(i, self._output_port_sel_addr.width)))

            self.add_child(f"tb_write_addr_gen_{i}",
                           AddrGen(iterator_support=loop_itr,
                                   config_width=loop_wth),
                           clk=self._clk,
                           rst_n=self._rst_n,
                           step=self._read_d1 & (self._output_port_sel_addr ==
                                                 const(i, self._output_port_sel_addr.width)),
                           mux_sel=fl_ctr_tb_wr.ports.mux_sel_out,
                           addr_out=self._tb_write_addr[i])

            fl_ctr_tb_rd = ForLoop(iterator_support=2,
                                   config_width=16)
            loop_itr = fl_ctr_tb_rd.get_iter()
            loop_wth = fl_ctr_tb_rd.get_cfg_width()

            self.add_child(f"loops_buf2out_read_{i}",
                           fl_ctr_tb_rd,
                           clk=self._clk,
                           rst_n=self._rst_n,
                           step=self._tb_read[i])

            self.add_child(f"tb_read_addr_gen_{i}",
                           AddrGen(iterator_support=loop_itr,
                                   config_width=6),
                           clk=self._clk,
                           rst_n=self._rst_n,
                           step=self._tb_read[i],
                           mux_sel=fl_ctr_tb_rd.ports.mux_sel_out,
                           addr_out=self._tb_read_addr[i])

            self.add_child(f"tb_read_sched_gen_{i}",
                           SchedGen(iterator_support=loop_itr,
                                    config_width=16),
                           clk=self._clk,
                           rst_n=self._rst_n,
                           cycle_count=self._cycle_count,
                           mux_sel=fl_ctr_tb_rd.ports.mux_sel_out,
                           valid_output=self._tb_read[i])

        if self.interconnect_output_ports > 1:

            fl_ctr_out_sel = ForLoop(iterator_support=2,
                                     config_width=clog2(self.interconnect_output_ports))
            loop_itr = fl_ctr_out_sel.get_iter()
            loop_wth = fl_ctr_out_sel.get_cfg_width()

            self.add_child(f"loops_buf2out_out_sel",
                           fl_ctr_out_sel,
                           clk=self._clk,
                           rst_n=self._rst_n,
                           step=self._read_d1)

            self.add_child(f"out_port_sel_addr",
                           AddrGen(iterator_support=loop_itr,
                                   config_width=loop_wth),
                           clk=self._clk,
                           rst_n=self._rst_n,
                           step=self._read_d1,
                           mux_sel=fl_ctr_out_sel.ports.mux_sel_out,
                           addr_out=self._output_port_sel_addr)
            # Addr for port select should be driven on agg to sram write sched
        else:
            self.wire(self._output_port_sel_addr[0], const(0, self._output_port_sel_addr.width))

        # lift_config_reg(self.internal_generator)

        # self.add_code(self.set_sram_addr)

        self.add_code(self.tb_ctrl)
        for idx in range(self.interconnect_output_ports):
            self.add_code(self.tb_to_out, idx=idx)

    @always_ff((posedge, "clk"))
    def agg_ctrl(self, idx):
        if self._agg_write[idx]:
            self._agg[idx][self._agg_write_addr[idx][self._agg_write_addr[0].width - 1, 2]]\
                          [self._agg_write_addr[idx][1, 0]] = self._data_in[idx]

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def delay_read(self):
        if ~self._rst_n:
            self._read_d1 = 0
        else:
            self._read_d1 = self._read

    @always_ff((posedge, "clk"))
    def tb_ctrl(self):
        if self._read_d1:
            self._tb[self._output_port_sel_addr][self._tb_write_addr[self._output_port_sel_addr][1, 0]] = \
                self._sram_read_data

    @always_comb
    def tb_to_out(self, idx):
        self._data_out[idx] = self._tb[idx][self._tb_read_addr[idx][3, 2]][self._tb_read_addr[idx][1, 0]]

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def increment_cycle_count(self):
        if ~self._rst_n:
            self._cycle_count = 0
        else:
            self._cycle_count = self._cycle_count + 1


if __name__ == "__main__":
    lake_dut = StrgUB()
    verilog(lake_dut, filename="strg_ub_new.sv",
            optimize_if=False,
            additional_passes={"lift config regs": lift_config_reg})
