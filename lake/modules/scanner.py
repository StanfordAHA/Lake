import kratos as kts
from kratos import *
from lake.passes.passes import lift_config_reg
from lake.modules.for_loop import ForLoop
from lake.modules.addr_gen import AddrGen
from lake.utils.util import add_counter, safe_wire, trim_config_list
from lake.attributes.formal_attr import FormalAttr, FormalSignalConstraint
from lake.attributes.config_reg_attr import ConfigRegAttr
from lake.attributes.control_signal_attr import ControlSignalAttr
from _kratos import create_wrapper_flatten
from lake.modules.reg_fifo import RegFIFO

class Scanner(Generator):
    def __init__(self,
                 data_width=16):

        super().__init__("scanner", debug=True)

        self.data_width = data_width
        self.add_clk_enable = True
        self.add_flush = True

        self.total_sets = 0

        # inputs
        self._clk = self.clock("clk")
        self._clk.add_attribute(FormalAttr(f"{self._clk.name}", FormalSignalConstraint.CLK))
        self._rst_n = self.reset("rst_n")
        self._rst_n.add_attribute(FormalAttr(f"{self._rst_n.name}", FormalSignalConstraint.RSTN))
        self._clk_en = self.clock_en("clk_en", 1)

        # Enable/Disable tile
        self._tile_en = self.input("tile_en", 1)
        self._tile_en.add_attribute(ConfigRegAttr("Tile logic enable manifested as clock gate"))

        gclk = self.var("gclk", 1)
        self._gclk = kts.util.clock(gclk)
        self.wire(gclk, kts.util.clock(self._clk & self._tile_en))

        # Scanner interface will need
        # input data, input valid
        # output address, output valid
        self._data_in = self.input("data_in", self.data_width)
        self._data_in.add_attribute(ControlSignalAttr(is_control=False, full_bus=True))

        self._valid_in = self.input("valid_in", 1)
        self._valid_in.add_attribute(ControlSignalAttr(is_control=True))

        self._ready_in = self.input("ready_in", 1)
        self._ready_in.add_attribute(ControlSignalAttr(is_control=True))

        self._ready_out = self.output("ready_out", 1)
        self._ready_out.add_attribute(ControlSignalAttr(is_control=False))
        
        self._data_out = self.output("data_out", self.data_width)
        self._data_out.add_attribute(ControlSignalAttr(is_control=False, full_bus=True))

        self._valid_out = self.output("valid_out", 1)
        self._valid_out.add_attribute(ControlSignalAttr(is_control=False))

        self._addr_out = self.output("addr_out", self.data_width)
        self._addr_out.add_attribute(ControlSignalAttr(is_control=False, full_bus=True))

        self._eos_out = self.output("eos_out", 1)
        self._eos_out.add_attribute(ControlSignalAttr(is_control=False))

        # Intermediate for typing...
        self._ren = self.var("ren", 1)

# ==========================================
# Generate addresses to scan over fiber...
# ==========================================

        # Create read address generator
        self.FIBER_READ_ITER = ForLoop(iterator_support=2,
                                config_width=16)
        self.FIBER_READ_ADDR = AddrGen(iterator_support=2,
                                config_width=16)

        self.add_child(f"fiber_read_iter",
                        self.FIBER_READ_ITER,
                        clk=self._gclk,
                        rst_n=self._rst_n,
                        step=self._ren)

        # Whatever comes through here should hopefully just pipe through seamlessly
        # addressor modules

        self.add_child(f"fiber_read_addr",
                        self.FIBER_READ_ADDR,
                        clk=self._gclk,
                        rst_n=self._rst_n,
                        step=self._ren,
                        mux_sel=self.FIBER_READ_ITER.ports.mux_sel_out,
                        restart=self.FIBER_READ_ITER.ports.restart)
        safe_wire(self, self._addr_out, self.FIBER_READ_ADDR.ports.addr_out)

        self._iter_restart = self.var("iter_restart", 1)
        self.wire(self._iter_restart, self.FIBER_READ_ITER.ports.restart)

# ===================================
# Dump metadata into fifo
# ===================================

        # Stupid convert -
        self._data_in_packed = self.var("fifo_in_packed", self.data_width + 1, packed=True)
        self._last_valid_accepting = self.var("last_valid_accepting", 1)
        # The EOS tags on the last valid in the stream
        self.wire(self._data_in_packed[self.data_width], self._last_valid_accepting)
        self.wire(self._data_in_packed[self.data_width - 1, 0], self._data_in)

        self._data_out_packed = self.var("fifo_out_packed", self.data_width + 1, packed=True)
        self.wire(self._eos_out, self._data_out_packed[self.data_width])
        self.wire(self._data_out, self._data_out_packed[self.data_width - 1, 0])

        self._rfifo = RegFIFO(data_width=self.data_width + 1, width_mult=1, depth=8)

        # Gate ready after last read in the stream
        self._ready_gate = self.var("ready_gate", 1)
        @always_ff((posedge, "clk"), (negedge, "rst_n"))
        def ready_gate_ff():
            if ~self._rst_n:
                self._ready_gate = 0
            elif self._iter_restart:
                self._ready_gate = 1
        self.add_code(ready_gate_ff)

        self.add_child(f"coordinate_fifo",
                       self._rfifo,
                       clk=self._gclk,
                       rst_n=self._rst_n,
                       clk_en=self._clk_en,
                       push=self._valid_in,
                       pop=(self._valid_out & self._ready_in),
                       data_in=self._data_in_packed,
                       data_out=self._data_out_packed,
                       valid=self._valid_out)

        self.wire(self._ren, ~self._rfifo.ports.almost_full & ~self._ready_gate)
        self.wire(self._ready_out, self._ren)

        self._fifo_full = self.var("fifo_full", 1)
        self.wire(self._fifo_full, self._rfifo.ports.full)
        # Increment valid count when we receive a valid we can actually push in the FIFO
        self._valid_cnt = add_counter(self, "valid_count", 16, self._valid_in & (~self._fifo_full))

        self._stream_length = self.input("stream_length", 16)
        self._stream_length.add_attribute(ConfigRegAttr("How long is the stream..."))

        @always_comb
        def eos_comparison():
            self._last_valid_accepting = (self._valid_cnt == self._stream_length) & (self._valid_in)
        self.add_code(eos_comparison)

        if self.add_clk_enable:
            # self.clock_en("clk_en")
            kts.passes.auto_insert_clock_enable(self.internal_generator)
            clk_en_port = self.internal_generator.get_port("clk_en")
            clk_en_port.add_attribute(ControlSignalAttr(False))

        if self.add_flush:
            self.add_attribute("sync-reset=flush")
            kts.passes.auto_insert_sync_reset(self.internal_generator)
            flush_port = self.internal_generator.get_port("flush")
            flush_port.add_attribute(ControlSignalAttr(True))

        # Finally, lift the config regs...
        lift_config_reg(self.internal_generator)

    def get_bitstream(self, length):

        # Store all configurations here
        config = [("fiber_read_addr_starting_addr", 0),
                  ("fiber_read_iter_dimensionality", 1),
                  ("fiber_read_addr_strides_0", 1),
                #   ("fiber_read_addr_strides_1", 0),
                  ("fiber_read_iter_ranges_0", length - 2),
                  ("fiber_read_iter_ranges_1", 0),
                  ("stream_length", length - 1)
                  ]
        # Dummy variables to fill in later when compiler
        # generates different collateral for different designs
        # flattened = create_wrapper_flatten(self.internal_generator.clone(),
        #                                    self.name + "_W")

        # # Trim the list
        # return trim_config_list(flattened, config)
        return config


if __name__ == "__main__":
    scanner_dut = Scanner(data_width=16)

    # Lift config regs and generate annotation
    # lift_config_reg(pond_dut.internal_generator)
    # extract_formal_annotation(pond_dut, "pond.txt")

    verilog(scanner_dut, filename="scanner.sv",
            optimize_if=False)
