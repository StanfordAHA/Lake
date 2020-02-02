from lake.models.tb_model import TBModel
from lake.modules.transpose_buffer import TransposeBuffer
import magma as m
from magma import *
import fault
import tempfile
import kratos as k
import random as rand
import pytest


@pytest.mark.skip
def test_tb(word_width=16,
            fetch_width=4,
            num_tb=1,
            tb_height=1,
            max_range=5):

    model_tb = TBModel(word_width,
                       fetch_width,
                       num_tb,
                       tb_height,
                       max_range)

    new_config = {}
    new_config["range_outer"] = 5
    new_config["range_inner"] = 3
    new_config["stride"] = 2
    new_config["indices"] = [0, 1, 2]

    model_tb.set_config(new_config=new_config)

    dut = TransposeBuffer(word_width,
                          fetch_width,
                          num_tb,
                          tb_height,
                          max_range)

    magma_dut = k.util.to_magma(dut, flatten_array=True)
    tester = fault.Tester(magma_dut, magma_dut.clk)

    tester.circuit.clk = 0
    tester.circuit.rst_n = 1
    tester.step(2)
    tester.circuit.rst_n = 0
    tester.step(2)
    tester.circuit.rst_n = 1

    data = []
    for i in range(64):
        data.append(i)

    # configuration registers
    tester.circuit.indices_0 = 0
    tester.circuit.indices_1 = 1
    tester.circuit.indices_2 = 2

    tester.circuit.range_outer = 5
    tester.circuit.range_inner = 3
    tester.circuit.stride = 2

    num_iters = 5
    for i in range(num_iters):
        print()
        print("i: ", i)

        for j in range(fetch_width):
            setattr(tester.circuit, f"input_data_{j}", data[(i * fetch_width + j) % 50])
        # add testing a few dead valid cycles
        if i == 0:
            valid_data = 1
        elif i == 1 or i == 2 or i == 3:
            valid_data = 0
        elif i == 4:
            valid_data = 1
        elif 4 < i < 9:
            valid_data = 0
        elif (i - 9) % 6 == 0:
            valid_data = 1
        else:
            valid_data = 0

        tester.circuit.valid_data = valid_data

        input_data = data[i * fetch_width % 50:(i * fetch_width + 4) % 50]

        ack_in = valid_data
        tester.circuit.ack_in = ack_in

        if len(input_data) != fetch_width:
            input_data = data[0:4]
        print("input data: ", input_data)

        model_data, model_valid, model_rdy_to_arbiter = \
            model_tb.transpose_buffer(input_data, valid_data, ack_in)

        tester.eval()
        # if i < num_iters - 50:
        tester.circuit.output_valid.expect(model_valid)
        # tester.circuit.rdy_to_arbiter.expect(model_rdy_to_arbiter)
        print("model rdy: ", model_rdy_to_arbiter)
        print("model output valid: ", model_valid)
        print(model_data[0])
        if model_valid:
            tester.circuit.col_pixels.expect(model_data[0])

        tester.step(2)

    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = "tb_dump"
        tester.compile_and_run(target="verilator",
                               directory=tempdir,
                               magma_output="verilog",
                               flags=["-Wno-fatal", "--trace"])
