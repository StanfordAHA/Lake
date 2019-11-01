from kratos import *
from math import log

class TransposeBuffer(Generator):
    def __init__(self, word_width, mem_word_width, range_, stride, stencil_height):
        super().__init__("transpose_buffer")

        # inputs
        self.clk = self.clock("clk")
        # active low asynchronous reset
        self.rst = self.reset("rst", 1)
        self.mem_data = self.input("mem_data", width=word_width, size=mem_word_width)
        self.valid_input = self.input("valid_input", width=1, size=mem_word_width)
        
        # outputs
        self.col_pixels = self.output("col_pixels", width=word_width, size=stencil_height)
        self.read_valid = self.output("read_valid", 1)
        self.stencil_valid = self.output("stencil_valid", 1)

        # local variables
        self.tb = self.var("tb", width=mem_word_width, size=2*stencil_height)
        self.indices = self.var("indices", width=clog2(mem_word_width), size=mem_word_width)
        self.col_index = self.var("col_index", clog2(mem_word_width))
        self.num_valid = self.var("num_valid", clog2(mem_word_width))
        self.row_index = self.var("row_index", clog2(stencil_height))

        # sequential blocks
        self.add_code(self.get_valid_indices)
        self.add_code(self.in_buf)
        self.add_code(self.update_index_vars)
        self.add_code(self.out_buf)

        # combinational blocks
        self.add_code(self.dummy_func)

    #updating index variables
    @always((posedge, "clk"))
    def update_index_vars(self):
        if (self.rst == 0):
            self.col_index = 0
            self.row_index = 0
        # assuming mem_word_width == stencil_height FOR NOW TO DO CHANGE
        elif (self.col_index == mem_word_width - 1):
            self.col_index = 0
            self.row_index
        else:
            self.col_index = self.col_index + const(1, clog2(mem_word_width))
            self.row_index = self.row_index + const(1, clog2(stencil_height))

    # setting valid outputs
    def dummy_func(self):
        self.read_valid = 1
        self.stencil_valid = 1

    #update transpose buffer with data from memory
    @always((posedge, "clk"))
    def get_valid_indices(self):
        self.num_valid = mem_word_width - 1
        for i in range(mem_word_width):
            self.indices[i] = i
        for i in range(mem_word_width):
            if self.valid_input[i] == 0:
                for j in range(i, mem_word_width - 1):
                    self.indices[i] = self.indices[i+1]
                self.num_valid = self.num_valid - 1

    @always((posedge, "clk"))
    def in_buf(self):
        for i in range(mem_word_width):
            self.tb[self.row_index][i] = self.mem_data[self.indices[i]]

    # output appropriate data from transpose buffer
    @always((posedge, "clk"))
    def out_buf(self):
        for i in range(stencil_height):
            self.col_pixels[i] = self.tb[i][self.col_index]

dut = TransposeBuffer(8, 8, 1, 1, 8)
verilog(dut, filename="tb.v")
