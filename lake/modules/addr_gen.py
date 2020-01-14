from kratos import *
from functools import reduce
import operator

class AddrGen(Generator):
    '''
    Generate addresses for a single port
    '''
    def __init__(self, 
                 mem_depth, 
                # banks, 
                 iterator_support,
                 address_width):
        super().__init__("addr_gen_" + str(iterator_support), debug=True)
        #print("Making addrgen")
        #self.data_width = data_width
       # self.banks = banks
        self.mem_depth = mem_depth
        self.mem_addr_width = clog2(self.mem_depth)
        #self.bank_addr_width = clog2(self.banks)
        self.full_addr = self.mem_addr_width # + self.bank_addr_width
        self.iterator_support = iterator_support

        ##### PORT DEFS: begin

        ### INPUTS
        self._clk = self.clock("clk")
        self._rst_n = self.reset("rst_n")
        self._strides = self.input("strides", 32, size=self.iterator_support, packed=True, explicit_array=True)
        #self._strides = []
        #self._ranges = []
        #for i in range(self.iterator_support):
          #  self._strides.append(self.input(f"stride_{i}", 32))
        #    self._ranges.append(self.input(f"range_{i}", 32))


        self._ranges = self.input("ranges", 32, size=self.iterator_support, packed=True, explicit_array=True)
        self._starting_addr = self.input("starting_addr", 32) #, explicit_array=True)
        self._dimensionality = self.input("dimensionality", 4)
        self._step = self.input("step", 1)

        ### OUTPUTS
        self._addr_out = self.output("addr_out", 32)
        #self._addr_out = self.output("addr_out", self.mem_addr_width, size=self.banks, explicit_array=True, packed=True)

        ### MISC
        self._clk_en = self.input("clk_en", 1)
        self._flush = self.input("flush", 1)

        ##### PORT DEFS: end

        ##### LOCAL VARIABLES: begin
        self._current_loc = self.var("current_loc", 32, size=self.iterator_support, packed=True, explicit_array=True)

        #self._addr = self.var("addr", self.mem_addr_width)
        self._write_addr = self.var("write_addr", 32)
        self._dim_counter = self.var("dim_counter", 32, size=self.iterator_support, packed=True, explicit_array=True)

        self._update = self.var("update", self.iterator_support)
        self._strt_addr = self.var("strt_addr", 32)

        self._counter_update = self.var("counter_update", 1)
        self._calc_addr = self.var("calc_addr", 32)

        ##### LOCAL VARIABLES: end

        ##### GENERATION LOGIC: begin
        self.wire(self._strt_addr, self._starting_addr)

        self.wire(self._addr_out, self._calc_addr)

        # Set update vector

        self.wire(self._update[0],  const(1, 1))
        for i in range(self.iterator_support - 1):
            self.wire(self._update[i + 1], (self._dim_counter[i] == (self._ranges[i] - 1)) & self._update[i])

        self.add_code(self.calc_addr_comb)
        self.add_code(self.dim_counter_update)
        self.add_code(self.current_loc_update)

        ##### GENERATION LOGIC: end
    @always_comb
    def calc_addr_comb(self):
        self._calc_addr = reduce(operator.add, [(ternary(const(i, self._dimensionality.width) < self._dimensionality, self._current_loc[i], const(0, self._calc_addr.width))) for i in range(self.iterator_support)] + [self._strt_addr])

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def dim_counter_update(self):
        if ~self._rst_n:
            self._dim_counter = 0
        elif self._clk_en:
            if self._flush:
                for i in range(self.iterator_support):
                    self._dim_counter[i] = 0
            #elif self._autoswitch | self._switch:
            #    self._dim_counter[0] = concat(const(0, 31), self._range[0] > 1)
            #    for i in range(self.iterator_support - 1):
            #        self._dim_counter[i + 1] = 0
            elif (self._step):
                for i in range(self.iterator_support):
                    if self._update[i] & (i < self._dimensionality):
                        if self._dim_counter[i] == (self._ranges[i] - 1):
                            self._dim_counter[i] = 0
                        else:
                            self._dim_counter[i] = self._dim_counter[i] + 1

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def current_loc_update(self):
        if ~self._rst_n:
            self._current_loc = 0
        elif self._clk_en:
            if self._flush:
                #self._current_loc[0] = ternary(self._depth == 0, self._stride[0], const(0, self._current_loc[0].width))
                #self._current_loc[0] = ternary(self._depth == 0, self._stride[0], const(0, self._current_loc[0].width))
                for i in range(self.iterator_support):
                    self._current_loc[i] = 0
            #elif self._autoswitch | self._switch:
            #    self._current_loc[0] = self._stride[0]
            #    for i in range(self.iterator_support - 1):
            #        self._current_loc[i + 1] = 0
            elif self._step:
                for i in range(self.iterator_support):
                    if self._update[i] & (i < self._dimensionality):
                        if self._dim_counter[i] == (self._ranges[i] - 1):
                            self._current_loc[i] = 0
                        else:
                            self._current_loc[i] = self._current_loc[i] + self._strides[i]



if __name__ == "__main__":
    db_dut = AddrGen(mem_depth=512, iterator_support=6, address_width=16)
    verilog(db_dut, filename="addr_gen.sv", check_active_high=False)

