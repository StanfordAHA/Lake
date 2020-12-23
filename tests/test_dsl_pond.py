import kratos as kts
import fault
import random as rand
import pytest
import tempfile
from lake.utils.util import transform_strides_and_ranges, generate_pond_api
from lake.collateral2compiler.pond_dsl import *


def setup_test_pond():
    hw = pond.test_magma_lake()
    magma_dut = kts.util.to_magma(hw,
                                  flatten_array=True,
                                  check_multiple_driver=False,
                                  optimize_if=False,
                                  check_flip_flop_always_ff=False)

    tester = fault.Tester(magma_dut, magma_dut.clk)
    return magma_dut, tester


def test_pond_basic(data_width=16,  # CGRA Params
                    mem_depth=32,
                    default_iterator_support=2,
                    config_data_width=32,
                    config_addr_width=8,
                    cycle_count_width=16,
                    add_clk_enable=True,
                    add_flush=True,
                    interconnect_input_ports=1,  # Connection to int
                    interconnect_output_ports=1):

    magma_dut, tester = setup_test_pond()

    # Ranges, Strides, Dimensionality, Starting Addr
    # Starting Addr (schedule), Ranges (schedule)
    ctrl_rd = [[16, 1], [1, 1], 2, 0, 16, [1, 1]]
    ctrl_wr = [[16, 1], [1, 1], 2, 0, 0, [1, 1]]
    pond_config = generate_pond_api(ctrl_rd, ctrl_wr, True)

    for key, value in pond_config.items():
        setattr(tester.circuit, key, value)

    rand.seed(0)
    tester.circuit.clk = 0
    tester.circuit.clk_en = 1
    tester.circuit.tile_en = 1
    tester.circuit.rst_n = 0
    tester.step(1)
    tester.circuit.rst_n = 1
    tester.step(1)
    tester.circuit.clk_en = 1

    data_in_pond = [0] * interconnect_input_ports
    valid_in = [0] * interconnect_input_ports
    for i in range(32):
        # Incrementing Data
        data_in_pond[0] = data_in_pond[0] + 1

        if interconnect_input_ports == 1:
            tester.circuit.data_in = data_in_pond[0]
        else:
            for j in range(interconnect_input_ports):
                setattr(tester.circuit, f"data_in_{j}", data_in_pond[j])

        if i >= 16:
            tester.circuit.data_out.expect(i - 15)

        tester.eval()
        tester.step(2)

    with tempfile.TemporaryDirectory() as tempdir:
        tester.compile_and_run(target="verilator",
                               directory=tempdir,
                               magma_output="verilog",
                               flags=["-Wno-fatal"])


def test_pond_strided_read(data_width=16,  # CGRA Params
                           mem_depth=32,
                           default_iterator_support=2,
                           config_data_width=32,
                           config_addr_width=8,
                           cycle_count_width=16,
                           add_clk_enable=True,
                           add_flush=True,
                           interconnect_input_ports=1,  # Connection to int
                           interconnect_output_ports=1):

    # DUT
    pond_dut = Pond(data_width=data_width,  # CGRA Params
                    mem_depth=mem_depth,
                    default_iterator_support=default_iterator_support,
                    interconnect_input_ports=interconnect_input_ports,  # Connection to int
                    interconnect_output_ports=interconnect_output_ports,
                    config_data_width=config_data_width,
                    config_addr_width=config_addr_width,
                    cycle_count_width=cycle_count_width,
                    add_clk_enable=add_clk_enable,
                    add_flush=add_flush)

    magma_dut = kts.util.to_magma(pond_dut,
                                  flatten_array=True,
                                  check_multiple_driver=False,
                                  optimize_if=False,
                                  check_flip_flop_always_ff=False)

    tester = fault.Tester(magma_dut, magma_dut.clk)

    # Ranges, Strides, Dimensionality, Starting Addr
    # Starting Addr (schedule), Ranges (schedule)
    ctrl_rd = [[8, 1], [2, 0], 1, 0, 16, [1, 0]]
    ctrl_wr = [[16, 1], [1, 1], 1, 0, 0, [1, 1]]
    pond_config = generate_pond_api(ctrl_rd, ctrl_wr)

    for key, value in pond_config.items():
        setattr(tester.circuit, key, value)

    rand.seed(0)
    tester.circuit.clk = 0
    tester.circuit.clk_en = 1
    tester.circuit.tile_en = 1
    tester.circuit.rst_n = 0
    tester.step(1)
    tester.circuit.rst_n = 1
    tester.step(1)
    tester.circuit.clk_en = 1

    data_in_pond = [0] * interconnect_input_ports
    valid_in = [0] * interconnect_input_ports
    for i in range(24):
        # Incrementing Data
        data_in_pond[0] = data_in_pond[0] + 1

        if interconnect_input_ports == 1:
            tester.circuit.data_in_pond = data_in_pond[0]
        else:
            for j in range(interconnect_input_ports):
                setattr(tester.circuit, f"data_in_{j}", data_in_pond[j])
        if i >= 16:
            tester.circuit.data_out_pond.expect((i - 16) * 2 + 1)

        tester.eval()
        tester.step(2)

    with tempfile.TemporaryDirectory() as tempdir:
        tester.compile_and_run(target="verilator",
                               directory=tempdir,
                               magma_output="verilog",
                               flags=["-Wno-fatal"])


def test_pond_b2b_read(data_width=16,  # CGRA Params
                       mem_depth=32,
                       default_iterator_support=2,
                       config_data_width=32,
                       config_addr_width=8,
                       cycle_count_width=16,
                       add_clk_enable=True,
                       add_flush=True,
                       interconnect_input_ports=1,  # Connection to int
                       interconnect_output_ports=1):

    # DUT
    pond_dut = Pond(data_width=data_width,  # CGRA Params
                    mem_depth=mem_depth,
                    default_iterator_support=default_iterator_support,
                    interconnect_input_ports=interconnect_input_ports,  # Connection to int
                    interconnect_output_ports=interconnect_output_ports,
                    config_data_width=config_data_width,
                    config_addr_width=config_addr_width,
                    cycle_count_width=cycle_count_width,
                    add_clk_enable=add_clk_enable,
                    add_flush=add_flush)

    magma_dut = kts.util.to_magma(pond_dut,
                                  flatten_array=True,
                                  check_multiple_driver=False,
                                  optimize_if=False,
                                  check_flip_flop_always_ff=False)

    tester = fault.Tester(magma_dut, magma_dut.clk)
    # Ranges, Strides, Dimensionality, Starting Addr
    # Starting Addr (schedule), Ranges (schedule)
    ctrl_rd = [[16, 10], [1, 0], 2, 0, 16, [1, 16]]
    ctrl_wr = [[16, 1], [1, 1], 2, 0, 0, [1, 1]]
    pond_config = generate_pond_api(ctrl_rd, ctrl_wr)

    for key, value in pond_config.items():
        setattr(tester.circuit, key, value)

    rand.seed(0)
    tester.circuit.clk = 0
    tester.circuit.clk_en = 1
    tester.circuit.tile_en = 1
    tester.circuit.rst_n = 0
    tester.step(1)
    tester.circuit.rst_n = 1
    tester.step(1)
    tester.circuit.clk_en = 1

    data_in_pond = [0] * interconnect_input_ports
    valid_in = [0] * interconnect_input_ports
    for i in range(16 * 11):
        # Incrementing Data
        data_in_pond[0] = data_in_pond[0] + 1

        if interconnect_input_ports == 1:
            tester.circuit.data_in_pond = data_in_pond[0]
        else:
            for j in range(interconnect_input_ports):
                setattr(tester.circuit, f"data_in_{j}", data_in_pond[j])

        if i >= 16:
            tester.circuit.data_out_pond.expect(((i - 16) % 16) + 1)

        tester.eval()
        tester.step(2)

    with tempfile.TemporaryDirectory() as tempdir:
        tester.compile_and_run(target="verilator",
                               directory=tempdir,
                               magma_output="verilog",
                               flags=["-Wno-fatal"])
