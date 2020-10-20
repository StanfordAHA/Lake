from kratos import *
from functools import reduce
import operator
from lake.attributes.config_reg_attr import ConfigRegAttr
from lake.modules.addr_gen import AddrGen
from lake.passes.passes import lift_config_reg


class SchedGen(Generator):
    '''
    Generate schedule
    '''
    def __init__(self,
                 iterator_support=6,
                 config_width=16):

        super().__init__(f"sched_gen_{iterator_support}_{config_width}")

        self.iterator_support = iterator_support
        self.config_width = config_width

        # PORT DEFS: begin

        # INPUTS
        self._clk = self.clock("clk")
        self._rst_n = self.reset("rst_n")

        # OUTPUTS
        self._valid_output = self.output("valid_output", 1)

        # VARS
        self._valid_out = self.var("valid_out", 1)
        self._cycle_count = self.input("cycle_count", self.config_width)
        self._mux_sel = self.input("mux_sel", max(clog2(self.iterator_support), 1))
        self._addr_out = self.var("addr_out", self.config_width)

        # Receive signal on last iteration of looping structure and
        # gate the output...
        self._finished = self.input("finished", 1)
        self._valid_gate = self.var("valid_gate", 1)

        @always_ff((posedge, "clk"), (negedge, "rst_n"))
        def valid_gate_ff():
            if ~self._rst_n:
                self._valid_gate = 1
            # If we are finishing the looping structure, turn this off to implement one-shot
            elif self._finished:
                self._valid_gate = 0
        self.add_code(valid_gate_ff)

        # Compare based on minimum of addr + global cycle...
        self.c_a_cmp = min(self._cycle_count.width, self._addr_out.width)

        # PORT DEFS: end

        self.add_child(f"sched_addr_gen",
                       AddrGen(iterator_support=self.iterator_support,
                               config_width=self.config_width),

                       clk=self._clk,
                       rst_n=self._rst_n,
                       step=self._valid_out,
                       mux_sel=self._mux_sel,
                       addr_out=self._addr_out,
                       restart=const(0, 1))

        self.add_code(self.set_valid_out)
        self.add_code(self.set_valid_output)

    @always_comb
    def set_valid_out(self):
        self._valid_out = (self._cycle_count == self._addr_out) & self._valid_gate

    @always_comb
    def set_valid_output(self):
        self._valid_output = self._valid_out


if __name__ == "__main__":
    db_dut = SchedGen(iterator_support=6)
    verilog(db_dut,
            filename="sched_gen.sv",
            additional_passes={"lift config regs": lift_config_reg})
