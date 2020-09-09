from kratos import *
from functools import reduce
import operator
from lake.attributes.config_reg_attr import ConfigRegAttr
from lake.attributes.formal_attr import FormalAttr, FormalSignalConstraint


class AddrGen(Generator):
    '''
    Generate addresses for a single port
    '''
    def __init__(self,
                 iterator_support=6,
                 config_width=16):

        super().__init__(f"addr_gen", debug=True)

        self.iterator_support = iterator_support
        self.config_width = config_width
        # Create params for instancing this module...
        self.iterator_support_par = self.param("ITERATOR_SUPPORT", clog2(iterator_support) + 1, default_value=self.iterator_support)
        self.config_width_par = self.param("CONFIG_WIDTH", clog2(config_width) + 1, default_value=self.config_width)

        # PORT DEFS: begin

        # INPUTS
        self._clk = self.clock("clk")
        self._rst_n = self.reset("rst_n")

        self._strides = self.input("strides", self.config_width,
                                   size=self.iterator_support,
                                   packed=True, explicit_array=True)
        self._strides.add_attribute(ConfigRegAttr("Strides of address generator"))
        self._strides.add_attribute(FormalAttr(f"{self._strides.name}", FormalSignalConstraint.SOLVE))

        self._starting_addr = self.input("starting_addr", self.config_width)
        self._starting_addr.add_attribute(ConfigRegAttr("Starting address of address generator"))
        self._starting_addr.add_attribute(FormalAttr(f"{self._starting_addr.name}", FormalSignalConstraint.SOLVE))

        self._step = self.input("step", 1)

        # OUTPUTS
        # TODO why is this config width instead of address width?
        self._addr_out = self.output("addr_out", self.config_width)

        # PORT DEFS: end

        # LOCAL VARIABLES: begin
        self._strt_addr = self.var("strt_addr", self.config_width)

        self._calc_addr = self.var("calc_addr", self.config_width)

        self._max_value = self.var("max_value", self.iterator_support)

        # LOCAL VARIABLES: end
        # GENERATION LOGIC: begin
        self.wire(self._strt_addr, self._starting_addr)
        self.wire(self._addr_out, self._calc_addr)
        self._mux_sel = self.input("mux_sel", max(clog2(self.iterator_support), 1))

        self._current_addr = self.var("current_addr", self.config_width)
        # Calculate address by taking previous calculation and adding the muxed stride
        self.wire(self._calc_addr, self._strt_addr + self._current_addr)

        self.add_code(self.calculate_address)
        # GENERATION LOGIC: end

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def calculate_address(self):
        if ~self._rst_n:
            self._current_addr = 0
        elif self._step:
            self._current_addr = self._current_addr + self._strides[self._mux_sel]


if __name__ == "__main__":
    db_dut = AddrGen(iterator_support=6)
    verilog(db_dut, filename="addr_gen.sv")
