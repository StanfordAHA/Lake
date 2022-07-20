import kratos as kts
from kratos import *
from lake.passes.passes import lift_config_reg
from lake.modules.for_loop import ForLoop
from lake.modules.addr_gen import AddrGen
from lake.utils.util import add_counter, safe_wire, register, sticky_flag, transform_strides_and_ranges, trim_config_list
from lake.attributes.formal_attr import FormalAttr, FormalSignalConstraint
from lake.attributes.config_reg_attr import ConfigRegAttr
from lake.attributes.control_signal_attr import ControlSignalAttr
from _kratos import create_wrapper_flatten
from lake.modules.reg_fifo import RegFIFO


class IOCore(Generator):
    def __init__(self,
                 data_width=16,
                 tracks_supported: list = None,
                 fifo_depth=2,
                 use_17_to_16_hack=True):

        super().__init__("io_core", debug=True)

        self.data_width = data_width
        self.add_clk_enable = True
        self.add_flush = True
        self.fifo_depth = fifo_depth
        self.hack17_to_16 = use_17_to_16_hack

        if tracks_supported is None:
            self.tracks_supported = []
        else:
            self.tracks_supported = tracks_supported

        self.total_sets = 0

        # inputs
        self._clk = self.clock("clk")
        self._clk.add_attribute(FormalAttr(f"{self._clk.name}", FormalSignalConstraint.CLK))
        self._rst_n = self.reset("rst_n")
        self._rst_n.add_attribute(FormalAttr(f"{self._rst_n.name}", FormalSignalConstraint.RSTN))
        self._clk_en = self.clock_en("clk_en", 1)

        # Enable/Disable tile
        self._tile_en = self.var("tile_en", 1)
        self.wire(self._tile_en, kts.const(1, 1))
        # self._tile_en = self.input("tile_en", 1)
        self._tile_en_fake = self.input("tile_en_fake", 1)
        # self._tile_en.add_attribute(ConfigRegAttr("Tile logic enable manifested as clock gate"))
        self._tile_en_fake.add_attribute(ConfigRegAttr("Tile logic enable manifested as clock gate"))

        gclk = self.var("gclk", 1)
        self._gclk = kts.util.clock(gclk)
        self.wire(gclk, kts.util.clock(self._clk & self._tile_en))

        # OUTPUT STREAMS

        f2ios = []
        io2fs = []
        glb2ios = []
        io2glbs = []

        for track_len in self.tracks_supported:

            full_bus = track_len > 1
            is_control = track_len == 1

            using_17b = track_len == 17
            to_glb_width = track_len
            if self.hack17_to_16 and using_17b:
                print("USING 17 to 16 HACK")
                to_glb_width = 16

            tmp_f2io = self.input(f"f2io_{track_len}", track_len, packed=True)
            tmp_f2io.add_attribute(ControlSignalAttr(is_control=is_control, full_bus=full_bus))
            tmp_f2io_r = self.output(f"f2io_{track_len}_ready", 1)
            tmp_f2io_r.add_attribute(ControlSignalAttr(is_control=False, full_bus=False))
            tmp_f2io_v = self.input(f"f2io_{track_len}_valid", 1)
            tmp_f2io_v.add_attribute(ControlSignalAttr(is_control=True, full_bus=False))
            f2ios.append((tmp_f2io, tmp_f2io_r, tmp_f2io_v))

            tmp_glb2io = self.input(f"glb2io_{to_glb_width}", to_glb_width, packed=True)
            tmp_glb2io.add_attribute(ControlSignalAttr(is_control=is_control, full_bus=full_bus))
            tmp_glb2io_r = self.output(f"glb2io_{to_glb_width}_ready", 1)
            tmp_glb2io_r.add_attribute(ControlSignalAttr(is_control=False, full_bus=False))
            tmp_glb2io_v = self.input(f"glb2io_{to_glb_width}_valid", 1)
            tmp_glb2io_v.add_attribute(ControlSignalAttr(is_control=True, full_bus=False))
            glb2ios.append((tmp_glb2io, tmp_glb2io_r, tmp_glb2io_v))

            tmp_io2glb = self.output(f"io2glb_{to_glb_width}", to_glb_width, packed=True)
            tmp_io2glb.add_attribute(ControlSignalAttr(is_control=False, full_bus=full_bus))
            tmp_io2glb_r = self.input(f"io2glb_{to_glb_width}_ready", 1)
            tmp_io2glb_r.add_attribute(ControlSignalAttr(is_control=True, full_bus=False))
            tmp_io2glb_v = self.output(f"io2glb_{to_glb_width}_valid", 1)
            tmp_io2glb_v.add_attribute(ControlSignalAttr(is_control=False, full_bus=False))
            io2glbs.append((tmp_io2glb, tmp_io2glb_r, tmp_io2glb_v))

            tmp_io2f = self.output(f"io2f_{track_len}", track_len, packed=True)
            tmp_io2f.add_attribute(ControlSignalAttr(is_control=False, full_bus=full_bus))
            tmp_io2f_r = self.input(f"io2f_{track_len}_ready", 1)
            tmp_io2f_r.add_attribute(ControlSignalAttr(is_control=True, full_bus=False))
            tmp_io2f_v = self.output(f"io2f_{track_len}_valid", 1)
            tmp_io2f_v.add_attribute(ControlSignalAttr(is_control=False, full_bus=False))
            io2fs.append((tmp_io2f, tmp_io2f_r, tmp_io2f_v))

            ### Build in input and output fifos of depth 2
            # f2io -> io2glb fifo
            f2io_2_io2glb_fifo = RegFIFO(data_width=track_len, width_mult=1, depth=self.fifo_depth)

            self.add_child(f"f2io_2_io2glb_{track_len}",
                           f2io_2_io2glb_fifo,
                           clk=self._gclk,
                           rst_n=self._rst_n,
                           clk_en=self._clk_en,
                           push=tmp_f2io_v,
                           pop=tmp_io2glb_r,
                           data_in=tmp_f2io)

            if self.hack17_to_16 and using_17b:
                self.wire(tmp_io2glb, f2io_2_io2glb_fifo.ports.data_out[0][to_glb_width - 1, 0])
            else:
                self.wire(tmp_io2glb, f2io_2_io2glb_fifo.ports.data_out)

            self.wire(tmp_f2io_r, ~f2io_2_io2glb_fifo.ports.full)
            self.wire(tmp_io2glb_v, ~f2io_2_io2glb_fifo.ports.empty)

            # glb2io -> io2f fifo
            glb2io_2_io2f_fifo = RegFIFO(data_width=track_len, width_mult=1, depth=self.fifo_depth)

            self.add_child(f"glb2io_2_io2f_{track_len}",
                           glb2io_2_io2f_fifo,
                           clk=self._gclk,
                           rst_n=self._rst_n,
                           clk_en=self._clk_en,
                           push=tmp_glb2io_v,
                           pop=tmp_io2f_r,
                           data_out=tmp_io2f)

            if self.hack17_to_16 and using_17b:
                self.wire(glb2io_2_io2f_fifo.ports.data_in[0][to_glb_width - 1, 0], tmp_glb2io)
                self.wire(glb2io_2_io2f_fifo.ports.data_in[0][to_glb_width], kts.const(0, 1))
            else:
                self.wire(glb2io_2_io2f_fifo.ports.data_in, tmp_glb2io)

            self.wire(tmp_glb2io_r, ~glb2io_2_io2f_fifo.ports.full)
            self.wire(tmp_io2f_v, ~glb2io_2_io2f_fifo.ports.empty)

    def get_bitstream(self):

        # Store all configurations here
        config = [("tile_en", 1),
                  ]
        return config


if __name__ == "__main__":

    io_core_dut = IOCore(data_width=16,
                         tracks_supported=[1, 17])

    # Lift config regs and generate annotation
    # lift_config_reg(pond_dut.internal_generator)
    # extract_formal_annotation(pond_dut, "pond.txt")
    verilog(io_core_dut, filename="iocore.sv",
            optimize_if=False)
