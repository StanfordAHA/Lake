from lake.spec.component import Component
from lake.utils.spec_enum import *
from lake.utils.util import add_counter
from lake.spec.iteration_domain import IterationDomain
import kratos as kts
from kratos import always_ff, always_comb, posedge, negedge


class ScheduleGenerator(Component):

    def __init__(self, dimensionality=6, stride_width=16, rv=False, name=None):
        self.mod_name = name
        if name is None:
            self.mod_name = f"sched_gen_{dimensionality}_{stride_width}"
        super().__init__(name=self.mod_name)
        self.dimensionality_support = dimensionality
        self.stride_width = stride_width
        self.rv = rv
        self.mod_name = name

    def get_rv(self):
        return self.rv

    def gen_hardware(self, id: IterationDomain = None, num_comparisons: int = 1, pos_reset=False):
        assert id is not None
        id_ext_width = id.get_extent_width()
        # Total cycle width right now is stride width + ext_width
        self.total_cycle_width = id_ext_width + self.stride_width + self.dimensionality_support + 1

        ##########
        ### IO ###
        ##########
        ### Config Regs
        self._strides = self.config_reg(name="strides", width=self.stride_width,
                                   size=self.dimensionality_support,
                                   packed=True, explicit_array=True)

        # Using stride width instead of total cycle to keep config reg smaller
        self._starting_cycle = self.config_reg(name="starting_cycle", width=self.stride_width)
        ### Inputs
        # self._clk = self.clock("clk")
        # self._rst_n = self.reset("rst_n")
        self._clk_ctr = add_counter(self, "clk_ctr", bitwidth=self.total_cycle_width, increment=kts.const(1, 1))

        self._flush = self.input("flush", 1)
        self.add_attribute("sync-reset=flush")
        self._mux_sel = self.input("mux_sel", max(kts.clog2(self.dimensionality_support), 1))
        # Use signals directly for now
        self._ctrs = self.input("iterators", id_ext_width,
                                   size=self.dimensionality_support,
                                   packed=True, explicit_array=True)

        ### Outputs
        self._step_out = self.output("step", 1)

        ### Local variables
        self._current_cycle = self.var("current_cycle", self.total_cycle_width)
        self._strt_cycle = self.var("strt_cycle", self.total_cycle_width)
        self._step = self.var("step_lcl", 1)

        ### Logic
        self.wire(self._strt_cycle, kts.ext(self._starting_cycle, self.total_cycle_width))
        self.wire(self._step_out, self._step & ~self._flush)

        # step is high when the current cycle matches the counter
        self.wire(self._step, self._clk_ctr == self._current_cycle)

        self.add_code(self.calculate_cycle_count)
        # self.add_code(self.calculate_cycle_delta)

        self.config_space_fixed = True
        self._assemble_cfg_memory_input()

    @always_comb
    def calculate_cycle_count(self):
        self._current_cycle = self._strt_cycle
        for i in range(self.dimensionality_support):
            self._current_cycle = self._current_cycle + self._ctrs[i] * self._strides[i]

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def calculate_cycle_delta(self):
        if ~self._rst_n:
            self._current_cycle = self._strt_cycle
        elif self._flush:
            self._current_cycle = self._strt_cycle
        elif self._step:
            self._current_cycle = self._current_cycle + self._strides[self._mux_sel]

    def gen_bitstream(self, schedule_map):
        assert 'strides' in schedule_map
        assert 'offset' in schedule_map
        self.configure(self._strides, schedule_map['strides'])
        self.configure(self._starting_cycle, schedule_map['offset'])
        # This will return pairs of ranges with values w.r.t. the node's configuration
        return self.get_configuration()

        return super().gen_bitstream()

    def get_step(self):
        return self._step_out

    def get_dimensionality(self):
        return self.dimensionality_support


class ExplicitScheduleGenerator(ScheduleGenerator):

    def __init__(self, dimensionality=16):
        super().__init__(dimensionality=dimensionality)

    def gen_hardware(self, pos_reset=False):
        return super().gen_hardware(pos_reset)

    def gen_bitstream(self):
        return super().gen_bitstream()


class RecurrentScheduleGenerator(ScheduleGenerator):

    def __init__(self, dimensionality=16):
        super().__init__(dimensionality=dimensionality)

    def gen_hardware(self, pos_reset=False):
        return super().gen_hardware(pos_reset)

    def gen_bitstream(self):
        return super().gen_bitstream()


class ReadyValidScheduleGenerator(ScheduleGenerator):

    def __init__(self, dimensionality=16, name=None):
        use_name = name
        if name is None:
            use_name = f"schedulegenerator_rv_dim_{dimensionality}"
        super().__init__(dimensionality=dimensionality, rv=True, name=use_name)
        self.num_comparisons = 1

    def get_num_comparisons(self):
        return self.num_comparisons

    def gen_hardware(self, id: IterationDomain = None, num_comparisons: int = 1, pos_reset=False):

        # Ready valid hardware implementation - just need the incoming iterators then to link up with all
        # others of this type
        assert id is not None
        self.num_comparisons = num_comparisons
        id_ext_width = id.get_extent_width()
        # Total cycle width right now is stride width + ext_width
        # self.total_cycle_width = id_ext_width + self.stride_width + self.dimensionality_support + 1

        # module_name = f"sched_gen_rv_{self.dimensionality_support}_{self.stride_width}"
        # super().__init__(mod_name=module_name)
        ##########
        ### IO ###
        ##########
        ### Config Regs
        ### Inputs
        # self._clk = self.clock("clk")
        # self._rst_n = self.reset("rst_n")
        self._flush = self.input("flush", 1)
        self.add_attribute("sync-reset=flush")

        # Still accept the iterators/mux_sel
        self._mux_sel = self.input("mux_sel", max(kts.clog2(self.dimensionality_support), 1))
        # Use signals directly for now
        self._ctrs = self.input("iterators", id_ext_width,
                                   size=self.dimensionality_support,
                                   packed=True, explicit_array=True)
        self._extents = self.input("extents", id_ext_width,
                                   size=self.dimensionality_support,
                                   packed=True, explicit_array=True)

        ### Outputs
        self._step_out = self.output("step", 1)
        # self._step_ack = self.output("step_ack", 1)

        ### Local variables
        # self._current_cycle = self.var("current_cycle", self.total_cycle_width)
        # self._strt_cycle = self.var("strt_cycle", self.total_cycle_width)
        self._step = self.var("step_lcl", 1)

        ### Logic
        # Gate the output step if flush is high.
        self.wire(self._step_out, self._step & ~self._flush)

        # step is high when the current cycle matches the counter
        # self.wire(self._step, self._clk_ctr == self._current_cycle)

        # Now we need to output the iterators and take in the comparisons
        self._iterators_out = self.output("iterators_out_lcl", id_ext_width,
                                   size=self.dimensionality_support,
                                   packed=True, explicit_array=True)
        self._extents_out = self.output("extents_out_lcl", id_ext_width,
                                   size=self.dimensionality_support,
                                   packed=True, explicit_array=True)

        self._comparisons_in = self.input("comparisons", self.num_comparisons)

        self.iterator_intf = {}
        self.iterator_intf['iterators'] = self._iterators_out
        self.iterator_intf['extents'] = self._extents_out
        self.iterator_intf['comparisons'] = self._comparisons_in

        # We define the step to be the reduction-and of all the in comparisons
        self.wire(self._step, self._comparisons_in.r_and())
        # Everything else will be qualified outside the module to go to the AG, ID

        self.wire(self._iterators_out, self._ctrs)
        for i in range(self.dimensionality_support):
            self.wire(self._extents_out[i], self._extents[i] + 2)
        # self.add_code(self.calculate_cycle_count)
        # self.add_code(self.calculate_cycle_delta)

        # this is the valid out
        self.config_space_fixed = True

    def get_iterator_intf(self):
        return self.iterator_intf

    def gen_bitstream(self, sched_map):
        return []
        # return super().gen_bitstream(schedule_map=sched_map)
