import kratos
from kratos import *
from math import log
from lake.attributes.config_reg_attr import ConfigRegAttr


class TransposeBuffer(Generator):
    def __init__(self,
                 # number of bits in a word
                 word_width,
                 # number of words that can be sotred at an address in SRAM
                 # note fetch_width must be powers of 2
                 fetch_width,
                 # total number of transpose buffers
                 num_tb,
                 # height of this particular transpose buffer
                 max_tb_height,
                 # maximum value for range parameters in nested for loop
                 # (and as a result, maximum length of indices input vector)
                 # specifying inner for loop values for output column
                 # addressing
                 max_range,
                 max_stride,
                 tb_iterator_support):
        super().__init__("transpose_buffer", True)

        #########################
        # GENERATION PARAMETERS #
        #########################

        self.word_width = word_width
        self.fetch_width = fetch_width
        self.num_tb = num_tb
        self.max_tb_height = max_tb_height
        self.max_range = max_range
        self.max_stride = max_stride
        self.tb_iterator_support = tb_iterator_support

        ##################################
        # BITS FOR GENERATION PARAMETERS #
        ##################################

        self.fetch_width_bits = max(1, clog2(self.fetch_width))
        self.num_tb_bits = max(1, clog2(self.num_tb))
        self.max_range_bits = max(1, clog2(self.max_range))
        self.max_stride_bits = max(1, clog2(self.max_stride))
        self.tb_col_index_bits = 2 * max(self.fetch_width_bits, self.num_tb_bits) + 1
        self.max_tb_height_bits2 = max(1, clog2(2 * self.max_tb_height))
        self.max_tb_height_bits = max(1, clog2(self.max_tb_height))
        self.tb_iterator_support_bits = max(1, clog2(self.tb_iterator_support) + 1)
        self.max_range_stride_bits2 = max(2 * self.max_range_bits, 2 * self.max_stride_bits)

        ##########
        # INPUTS #
        ##########

        self.clk = self.clock("clk")
        # active low asynchronous reset
        self.rst_n = self.reset("rst_n", 1)

        # data input from SRAM
        self.input_data = self.input("input_data",
                                     width=self.word_width,
                                     size=self.fetch_width,
                                     packed=True)
        # valid indicating whether data input from SRAM is valid and
        # should be stored in transpose buffer
        self.valid_data = self.input("valid_data", 1)

        self._ack_in = self.input("ack_in", 1)

        ###########################
        # CONFIGURATION REGISTERS #
        ###########################

        # the range of the outer for loop in nested for loop for output
        # column address generation
        self.range_outer = self.input("range_outer", self.max_range_bits)
        self.range_outer.add_attribute(ConfigRegAttr("Outer range for output for loop pattern"))

        # the range of the inner for loop in nested for loop for output
        # column address generation
        self.range_inner = self.input("range_inner", self.max_range_bits)
        self.range_inner.add_attribute(ConfigRegAttr("Inner range for output for for loop pattern"))

        # stride for the given application
        self.stride = self.input("stride", self.max_stride_bits)
        self.stride.add_attribute(ConfigRegAttr("Application stride"))

        self.tb_height = self.input("tb_height", self.max_tb_height_bits)
        self.tb_height.add_attribute(ConfigRegAttr("Transpose Buffer height"))

        self.dimensionality = self.input("dimensionality", self.tb_iterator_support_bits)
        self.dimensionality.add_attribute(ConfigRegAttr("Transpose Buffer dimensionality"))

        # specifies inner for loop values for output column
        # addressing
        self.indices = self.input("indices",
                                  width=clog2(2 * self.num_tb * self.fetch_width),
                                  # the length of indices is equal to range_inner,
                                  # so the maximum possible size for self.indices
                                  # is the maximum value of range_inner, which if
                                  # self.max_range_value
                                  size=self.max_range,
                                  packed=True)
        self.indices.add_attribute(ConfigRegAttr("Output indices for for loop pattern"))

        ###########
        # OUTPUTS #
        ###########

        self.col_pixels = self.output("col_pixels",
                                      width=self.word_width,
                                      size=self.max_tb_height,
                                      packed=True,
                                      explicit_array=True)
        self.output_valid = self.output("output_valid", 1)
        self.rdy_to_arbiter = self.output("rdy_to_arbiter", 1)

        ###################
        # LOCAL VARIABLES #
        ###################

        # transpose buffer
        self.tb = self.var("tb",
                           width=self.word_width,
                           size=[2 * self.max_tb_height, self.fetch_width],
                           packed=True)

        self.index_outer = self.var("index_outer", self.max_range_bits)
        self.index_inner = self.var("index_inner", self.max_range_bits)

        self.input_buf_index = self.var("input_buf_index", 1)
        self.out_buf_index = self.var("out_buf_index", 1)
        self.prev_out_buf_index = self.var("prev_out_buf_index", 1)
        self.row_index = self.var("row_index", self.max_tb_height_bits)
        self.input_index = self.var("input_index", self.max_tb_height_bits2)

        self.output_index_abs = self.var("output_index_abs", self.max_range_stride_bits2)
        self.output_index_long = self.var("output_index_long", self.max_range_stride_bits2)
        self.output_index = self.var("output_index", self.fetch_width_bits)
        self.indices_index_inner = self.var("indices_index_inner",
                                            clog2(2 * self.num_tb * self.fetch_width))
        self.curr_out_start = self.var("curr_out_start", self.max_range_stride_bits2)

        self.prev_output_valid = self.var("prev_output_valid", 1)

        self.start_data = self.var("start_data", 1)
        self.old_start_data = self.var("old_start_data", 1)

        self.pause_tb = self.var("pause_tb", 1)
        self.pause_output = self.var("pause_output", 1)
        self.prev_pause_output = self.var("prev_pause_output", 1)

        ##########################
        # SEQUENTIAL CODE BLOCKS #
        ##########################

        self.add_code(self.set_index_outer)
        self.add_code(self.set_index_inner)
        self.add_code(self.set_pause_tb)
        self.add_code(self.set_row_index)
        self.add_code(self.set_input_buf_index)
        self.add_code(self.input_to_tb)
        self.add_code(self.output_from_tb)
        self.add_code(self.set_prev_output_valid)
        self.add_code(self.set_output_valid)
        self.add_code(self.set_out_buf_index)
        self.add_code(self.set_rdy_to_arbiter)
        self.add_code(self.set_start_data)
        self.add_code(self.set_curr_out_start)
        self.add_code(self.set_prev_out_buf_index)
        self.add_code(self.set_output_index)
        self.add_code(self.set_prev_pause_output)
        self.add_code(self.set_old_start_data)

        #############################
        # COMBINATIONAL CODE BLOCKS #
        #############################

        self.add_code(self.set_pause_output)
        self.add_code(self.set_input_index)
        self.add_code(self.set_tb_out_indices)

    # get output loop iterators
    # set pause_tb signal to pause input/output depending on
    # output loop iterator values and valid_data
    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_index_outer(self):
        if ~self.rst_n:
            self.index_outer = 0
        elif self.dimensionality == 0:
            self.index_outer = 0
        elif self.dimensionality == 1:
            if self.index_outer == self.range_outer - 1:
                self.index_outer = 0
            elif self.pause_tb:
                self.index_outer = self.index_outer
            elif ~self.pause_output:
                self.index_outer = self.index_outer + 1
        else:
            if self.index_inner == self.range_inner - 1:
                if self.index_outer == self.range_outer - 1:
                    self.index_outer = 0
                else:
                    self.index_outer = self.index_outer + 1

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_index_inner(self):
        if ~self.rst_n:
            self.index_inner = 0
        elif self.dimensionality <= 1:
            self.index_inner = 0
        else:
            if self.index_inner == self.range_inner - 1:
                self.index_inner = 0
            elif self.pause_tb:
                self.index_inner = self.index_inner
            elif ~self.pause_output:
                self.index_inner = self.index_inner + 1

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_pause_tb(self):
        if ~self.rst_n:
            self.pause_tb = 1
        elif self.dimensionality == 0:
            self.pause_tb = 1
        elif self.dimensionality == 1:
            if self.index_outer == self.range_outer - 1:
                self.pause_tb = ~self.valid_data
            elif self.pause_tb:
                self.pause_tb = ~self.valid_data
            elif ~self.pause_output:
                self.pause_tb = 0
        else:
            if self.index_inner == self.range_inner - 1:
                if self.index_outer == self.range_outer - 1:
                    self.pause_tb = ~self.valid_data
                else:
                    self.pause_tb = 0
            elif self.pause_tb:
                self.pause_tb = ~self.valid_data
            elif ~self.pause_output:
                self.pause_tb = 0

    @always_comb
    def set_pause_output(self):
        if self.pause_tb:
            self.pause_output = 1
        elif self.start_data & ~self.old_start_data:
            self.pause_output = 1
        else:
            self.pause_output = 0

    # get index of row to fill in transpose buffer with input data
    # for one of the two buffers in double buffer
    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_row_index(self):
        if ~self.rst_n:
            self.row_index = 0
        elif self.dimensionality == 0:
            self.row_index = 0
        elif self.valid_data & self.row_index == self.tb_height - 1:
            self.row_index = 0
        elif self.valid_data:
            self.row_index = self.row_index + 1

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_input_buf_index(self):
        if ~self.rst_n:
            self.input_buf_index = 0
        elif self.valid_data & (self.row_index == self.tb_height - 1):
            self.input_buf_index = ~self.input_buf_index
        # else:
        #     self.input_buf_index = self.input_buf_index

    # for double buffer, get index of row to fill in transpose buffer
    # with input data
    @always_comb
    def set_input_index(self):
        if self.dimensionality == 0:
            self.input_index = 0
        elif self.input_buf_index:
            self.input_index = const(self.max_tb_height, self.max_tb_height_bits2) + \
                self.row_index.extend(self.max_tb_height_bits2)
        else:
            self.input_index = self.row_index.extend(self.max_tb_height_bits2)

    # input to transpose buffer
    @always_ff((posedge, "clk"))
    def input_to_tb(self):
        if self.valid_data:
            for i in range(self.fetch_width):
                if self.dimensionality == 0:
                    self.tb[self.input_index][i] = 0
                else:
                    self.tb[self.input_index][i] = self.input_data[i]

    # get relative output column index from absolute output column index
    @always_comb
    def set_tb_out_indices(self):
        if self.dimensionality == 0:
            self.indices_index_inner = 0
            self.output_index_abs = 0
        elif self.dimensionality == 1:
            self.indices_index_inner = 0
            self.output_index_abs = self.index_outer.extend(self.max_range_stride_bits2) * \
                self.stride.extend(self.max_range_stride_bits2)
        else:
            self.indices_index_inner = self.indices[self.index_inner]
            self.output_index_abs = self.index_outer.extend(self.max_range_stride_bits2) * \
                self.stride.extend(self.max_range_stride_bits2) \
                + self.indices_index_inner.extend(self.max_range_stride_bits2)
        self.output_index_long = self.output_index_abs % fetch_width

    # output column from transpose buffer
    @always_ff((posedge, "clk"))
    def output_from_tb(self):
        for i in range(max_tb_height):
            if i < self.tb_height:
                if self.dimensionality == 0:
                    self.col_pixels[i] = 0
                elif self.out_buf_index:
                    self.col_pixels[i] = self.tb[i][self.output_index]
                else:
                    self.col_pixels[i] = self.tb[i + self.max_tb_height][self.output_index]

    @always_ff((posedge, "clk"))
    def set_output_index(self):
        self.output_index = self.output_index_long[clog2(fetch_width) - 1, 0]

    # generates output valid and updates which buffer in double buffer to output from
    # appropriately
    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_prev_output_valid(self):
        if ~self.rst_n:
            self.prev_output_valid = 0
        elif self.dimensionality == 0:
            self.prev_output_valid = 0
        elif self.pause_tb | self.pause_output:
            self.prev_output_valid = 0
        #elif self.prev_pause_output & ~self.pause_output:
        #    self.output_valid = 0
        else:
            self.prev_output_valid = 1

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_output_valid(self):
        if ~self.rst_n:
            self.output_valid = 0
        else:
            # this is needed because there is a 2 cycle delay between index_outer and 
            # actual output - change in tb rewrite
            self.output_valid = self.prev_output_valid

    @always_ff((posedge, "clk"))
    def set_prev_pause_output(self):
        self.prev_pause_output = self.pause_output

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_out_buf_index(self):
        if ~self.rst_n:
            self.out_buf_index = 1
        elif (self.output_index_abs >= self.curr_out_start + self.fetch_width):
            self.out_buf_index = ~self.out_buf_index

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_curr_out_start(self):
        if ~self.rst_n:
            self.curr_out_start = 0
        elif self.dimensionality == 0:
            self.curr_out_start = 0
        elif (self.output_index_abs >= self.curr_out_start + self.fetch_width):
            self.curr_out_start = self.curr_out_start + self.fetch_width

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_prev_out_buf_index(self):
        if ~self.rst_n:
            self.prev_out_buf_index = 0
        else:
            self.prev_out_buf_index = self.out_buf_index

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_start_data(self):
        if ~self.rst_n:
            self.start_data = 0
        elif self.valid_data & ~self.start_data:
            self.start_data = 1

    @always_ff((posedge, "clk"))
    def set_old_start_data(self):
        self.old_start_data = self.start_data

    @always_ff((posedge, "clk"), (negedge, "rst_n"))
    def set_rdy_to_arbiter(self):
        if ~self.rst_n:
            self.rdy_to_arbiter = 1
        elif self.dimensionality == 0:
            self.rdy_to_arbiter = 0
        elif self.start_data & ~self.old_start_data:
            self.rdy_to_arbiter = 1
        elif self.prev_out_buf_index != self.out_buf_index:
            self.rdy_to_arbiter = 1
        elif self.tb_height != 1:
            if self.row_index != self.tb_height - 1:
                self.rdy_to_arbiter = 1
        elif self._ack_in:
            self.rdy_to_arbiter = 0
