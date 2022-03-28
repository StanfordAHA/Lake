import kratos as kts
from kratos import *
from lake.passes.passes import lift_config_reg
from lake.utils.util import add_counter, register, sticky_flag, trim_config_list
from lake.attributes.formal_attr import FormalAttr, FormalSignalConstraint
from lake.attributes.config_reg_attr import ConfigRegAttr
from lake.attributes.control_signal_attr import ControlSignalAttr
from _kratos import create_wrapper_flatten
from lake.modules.reg_fifo import RegFIFO


class Arbiter(Generator):
    def __init__(self,
                 ins=1,
                 algo="RR"):

        super().__init__(f"arbiter_{ins}_in_{algo}_algo", debug=True)

        self.add_clk_enable = True
        self.add_flush = True

        self.total_sets = 0

        self.ins = ins
        self.algo = algo

        # inputs
        self._clk = self.clock("clk")
        self._clk.add_attribute(FormalAttr(f"{self._clk.name}", FormalSignalConstraint.CLK))
        self._rst_n = self.reset("rst_n")
        self._rst_n.add_attribute(FormalAttr(f"{self._rst_n.name}", FormalSignalConstraint.RSTN))
        self._clk_en = self.clock_en("clk_en", 1)

        # # Enable/Disable tile
        # self._tile_en = self.input("tile_en", 1)
        # self._tile_en.add_attribute(ConfigRegAttr("Tile logic enable manifested as clock gate"))

        # Scanner interface will need
        # input data, input valid
        # output address, output valid
        # There is a data in (for lowest level values, other level coordinates) and for address on lowest level when doing dense
        self._request_in = self.input("request_in", self.ins)
        # self._data_in.add_attribute(ControlSignalAttr(is_control=False, full_bus=True))

        self._grant_out = self.output("grant_out", self.ins)
        # self._valid_in.add_attribute(ControlSignalAttr(is_control=True))

        # Indicate if we should even provide a grant output
        self._resource_ready = self.input("resource_ready", 1)

        self._grant_line = self.var("grant_line", self.ins)
        self._grant_line_ready = self.var("grant_line_ready", self.ins)

        if self.ins == 1:
            self.wire(self._grant_out[0], self._resource_ready)
            return

        # Algorithmically set grant line...
        if self.algo == "RR":
            @always_ff((posedge, self._clk), (negedge, self._rst_n))
            def grant_line_ff(self):
                if ~self._rst_n:
                    self._grant_line = 1
                else:
                    self._grant_line = kts.concat(self._grant_line[self.ins - 2, 0], self._grant_line[self.ins - 1])
        else:
            raise RuntimeError("No supported algorithm for arbiter...")
        self.add_code(grant_line_ff)

        # Now deal with no request/no ready
        for i in range(self.ins):
            self.wire(self._grant_line_ready[i], self._grant_line[i] & self._resource_ready)
            self.wire(self._grant_out[i], self._grant_line_ready[i] & self._request_in[i])

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
        # lift_config_reg(self.internal_generator)

    def get_bitstream(self):

        flattened = create_wrapper_flatten(self.internal_generator.clone(),
                                           self.name + "_W")

        # Store all configurations here
        config = []

        return trim_config_list(flattened, config)


if __name__ == "__main__":
    arbiter_dut = Arbiter(ins=2, algo="RR")

    # Lift config regs and generate annotation
    # lift_config_reg(pond_dut.internal_generator)
    # extract_formal_annotation(pond_dut, "pond.txt")

    verilog(arbiter_dut, filename="arbiter.sv",
            optimize_if=False)
