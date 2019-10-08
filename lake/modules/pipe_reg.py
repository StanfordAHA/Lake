from kratos import *

class PipeReg(Generator):
    def __init__(self, data_width, stages):
        super().__init__(f"pipe_reg_{stages}")
        self._in = self.input("i_data_in", data_width)
        self._out = self.output("o_data_out", data_width)
        self._clk = self.clock("i_clk")
        self._rst_n = self.reset("i_rst_n")
        self._clk_en = self.input("i_clk_en", 1)

        self._reg_array = self.var("reg_array", data_width, size=stages, packed=True)
        self.stages = stages
        self.add_code(self.stage_elab)
        self.add_code(self.set_out)

    @always((posedge, "i_clk"), (negedge, "i_rst_n"))
    def stage_elab(self):
        if ~self._rst_n:
            self._reg_array = 0
        elif self._clk_en:
            self._reg_array[0] = self._in
            for i in range(self.stages - 1):
                self._reg_array[i+1] = self._reg_array[i]

    @always((posedge, "i_clk"), (negedge, "i_rst_n"))
    def set_out(self):
        if ~self._rst_n:
            self._out = 0
        elif self._clk_en:
            self._out = self._reg_array[self.stages - 1]


if __name__ == "__main__":
    stages = 3
    piperegdut = PipeReg(16, stages)
    verilog(piperegdut, filename=f"pipe_reg_{stages}.sv")

