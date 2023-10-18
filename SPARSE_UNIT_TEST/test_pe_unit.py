from lake.modules.onyx_pe import *
from lake.modules.onyx_pe_intf import *
import magma as m
from magma import *
import tempfile
import kratos as k

import sparse_helper
from sparse_helper import convert_stream_to_onyx_interp
from sam.sim.src.base import remove_emptystr
# from sam.sim.src.joiner import Intersect2
from sam.sim.test.test import TIMEOUT
from hwtypes import SIntVector, UIntVector, BitVector, Bit
from lassen.utils import float2bfbin, bfbin2float

from peak.family import PyFamily
from lassen.sim import PE_fc as lassen_fc
import lassen.asm as asm



import subprocess
import os
import random
random.seed(15)
import string

def init_module():
    dut = OnyxPE(data_width=16,
                 fifo_depth=2,
                 defer_fifos=False,
                 ext_pe_prefix="PE_GEN_",
                 pe_ro=True,
                 do_config_lift=False,
                 add_flush=True,
                 perf_debug=False)
    verilog(dut, filename=f"./modules/PE.sv",
            optimize_if=False)
    sparse_helper.update_tcl("pe_tb")
    dut = OnyxPEInterface(data_width=16)
    verilog(dut, filename=f"./modules/PEInterface.sv",
            optimize_if=False)

def load_test_module(test_name):
    gold_data_p = []

    in_data0 = [1, 'S1', 'D']
    in_data1 = [1, 'S1', 'D']
    in_data2 = [1, 'S1', 'D']

    if test_name == "basic_add":
        in_data0 = [1, 'S0', 0, 1, 2, 'S1', 'D']
        in_data1 = [2, 'S0', 1, 2, 3, 'S1', 'D']
        gold_data = [3, 'S0', 1, 3, 5, 'S1', 'D']
    elif test_name == "basic_sub":
        in_data0 = [3, 'S0', 1, 3, 5, 'S1', 'D']
        in_data1 = [2, 'S0', 1, 2, 3, 'S1', 'D']
        gold_data = [1, 'S0', 0, 1, 2, 'S1', 'D']
    elif test_name == "basic_umult0":
        in_data0 = [3, 'S0', 1, 3, 5, 'S1', 'D']
        in_data1 = [2, 'S0', 1, 2, 3, 'S1', 'D']
        gold_data = [6, 'S0', 1, 6, 15, 'S1', 'D']
    elif test_name == "basic_smult0":
        in_data0 = [3, 'S0', 1, 3, 5, 'S1', 'D']
        in_data1 = [2, 'S0', 1, 2, 3, 'S1', 'D']
        gold_data = [6, 'S0', 1, 6, 15, 'S1', 'D']
    elif test_name == "basic_abs":
        # TODO negative values are not well supported rn 
        in_data0 = [-1, 'S0', -1, -3, -5, 'S1', 'D']
        in_data1 = []
        gold_data = [1, 'S0', 1, 3, 5, 'S1', 'D']
    elif test_name == "basic_urelu":
        in_data0 = [1, 'S0', 1, 3, 5, 'S1', 'D']
        in_data1 = [2, 'S0', 1, 2, 3, 'S1', 'D']
        gold_data = [2, 'S0', 1, 2, 3, 'S1', 'D']
    elif test_name == "basic_srelu":
        in_data0 = [1, 'S0', 1, 3, 5, 'S1', 'D']
        in_data1 = [-2, 'S0', 1, 2, -3, 'S1', 'D']
        gold_data = [0, 'S0', 1, 2, 0, 'S1', 'D']
    elif test_name == "basic_or":
        in_data0 = [1, 'S0', 0, 0, 5, 'S1', 'D']
        in_data1 = [2, 'S0', 0, 2, 0, 'S1', 'D']
        gold_data = [3, 'S0', 0, 2, 5, 'S1', 'D']
    elif test_name == "basic_shl":
        in_data0 = [1, 'S0', 0, 0, 5, 'S1', 'D']
        in_data1 = [2, 'S0', 0, 2, 1, 'S1', 'D']
        gold_data = [4, 'S0', 0, 0, 10, 'S1', 'D']
    elif test_name == "basic_crop":
        in_data0 = [10, 'S0', 3, 4, 5, 'S1', 'D']
        in_data1 = [5, 'S0', 12, 1, 4, 'S1', 'D']
        in_data2 = [1, 'S0', 1, 2, 3, 'S1', 'D']
        gold_data = [5, 'S0', 3, 2, 4, 'S1', 'D']
    elif test_name == "basic_fp_add":
        #TODO generate different numbers
        Data = BitVector[16]
        inst = asm.fp_add()
        binary_string = float2bfbin(4.0)
        num = int(binary_string, 2)
        data0 = Data(num)
        data1 = Data(num)
        PE = lassen_fc(PyFamily())
        pe = PE()
        res, res_p, _, _, _ = pe(inst, data0, data1)
        in_data0 = [data0.value, 'S0', data0.value, data0.value, data0.value, 'S1', 'D']
        in_data1 = [data0.value, 'S0', data0.value, data0.value, data0.value, 'S1', 'D']
        gold_data = [res.value, 'S0', res.value, res.value, res.value, 'S1', 'D']
    elif test_name == "basic_fp_max":
        #TODO generate different numbers
        Data = BitVector[16]
        inst = asm.fp_sub()
        binary_string = float2bfbin(3.0)
        binary_string2 = float2bfbin(4.0)
        num = int(binary_string, 2)
        num2 = int(binary_string2, 2)
        data0 = Data(num)
        data1 = Data(num2)
        PE = lassen_fc(PyFamily())
        pe = PE()
        res, res_p, _, _, _ = pe(inst, data0, data1)
        in_data0 = [data0.value, 'S0', data0.value, data1.value, data1.value, 'S1', 'D']
        in_data1 = [data1.value, 'S0', data0.value, data1.value, data0.value, 'S1', 'D']
        gold_data = [data1.value, 'S0', data0.value, data1.value, data1.value, 'S1', 'D']
    elif test_name == "basic_fp_relu":
        #TODO generate different numbers
        Data = BitVector[16]
        inst = asm.fp_sub()
        binary_string = float2bfbin(-3.0)
        binary_string2 = float2bfbin(4.0)
        num = int(binary_string, 2)
        num2 = int(binary_string2, 2)
        data0 = Data(num)
        data1 = Data(num2)
        PE = lassen_fc(PyFamily())
        pe = PE()
        res, res_p, _, _, _ = pe(inst, data0, data1)
        in_data0 = [data0.value, 'S0', data0.value, data1.value, data1.value, 'S1', 'D']
        in_data1 = [data1.value, 'S0', data0.value, data1.value, 'S1', 'D']
        gold_data = [0, 'S0', 0, data1.value, data1.value, 'S1', 'D']

    in_data0 = convert_stream_to_onyx_interp(in_data0)
    in_data1 = convert_stream_to_onyx_interp(in_data1)
    in_data2 = convert_stream_to_onyx_interp(in_data2)
    gold_data = convert_stream_to_onyx_interp(gold_data)
    gold_data_p = convert_stream_to_onyx_interp(gold_data_p)

    return in_data0, in_data1, in_data2, gold_data, gold_data_p

def module_iter_basic(test_name, add_test=""):
    in_data0, in_data1, in_data2, gold_data, gold_data_p = load_test_module(test_name)

    sparse_helper.write_txt("in_data0.txt", in_data0)
    sparse_helper.write_txt("in_data1.txt", in_data1)
    sparse_helper.write_txt("in_data2.txt", in_data2)

    sparse_helper.clear_txt("out_data.txt")
    sparse_helper.clear_txt("out_data_p.txt")

    # find instruction
    instr_type = strip_modifiers(lassen_fc.Py.input_t.field_dict['inst'])
    asm_ = Assembler(instr_type)

    num_inputs = 0b011
    compare = 0
    if test_name == "basic_add":
        op = asm.add()
    elif test_name == "basic_umult0":
        op = asm.umult0()
    elif test_name == "basic_smult0":
        op = asm.smult0()
    elif test_name == "basic_sub":
        op = asm.sub()
    elif test_name == "basic_or":
        op = asm.or_()
    elif test_name == "basic_shl":
        op = asm.lsl()
    elif test_name == "basic_fp_add":
        op = asm.fp_add()
    elif test_name == "basic_fp_max":
        op = asm.fp_max()
    elif test_name == "basic_crop":
        op = asm.crop()
        num_inputs = 0b111
    # 1 input
    elif test_name == "basic_abs":
        op = asm.abs()
        num_inputs = 0b001
    elif test_name == "basic_urelu":
        op = asm.umax()
        num_inputs = 0b010
    elif test_name == "basic_srelu":
        op = asm.smax()
        num_inputs = 0b010
    elif test_name == "basic_fp_relu":
        op = asm.fp_relu()
        num_inputs = 0b001

    print(num_inputs)

    config = hex(int(asm_.assemble(op)))
    print(config)
    


    sim_result = subprocess.run(["make", "sim", "TEST_TAR=pe_tb.sv", "TOP=pe_tb",\
                             "TEST_UNIT=garnet.v", f"INST=+inst={config}", f"NUM_INPUTS=+num_inputs={num_inputs}"], capture_output=True, text=True)
    output = sim_result.stdout
    cycle_count_line = output[output.find("cycle count:"):]
    print(cycle_count_line.splitlines()[0])
    
    data_out = sparse_helper.read_txt("out_data.txt", addit=add_test != "")
    data_out_p = sparse_helper.read_txt("out_data_p.txt", addit=add_test != "")

    #compare each element in the output from data_out.txt with the gold output
    assert len(data_out) == len(gold_data), \
        f"Output length {len(data_out)} didn't match gold length {len(gold_data)}"

    if compare == 0:
        for i in range(len(data_out)):
            assert data_out[i] == gold_data[i], \
                f"Output {data_out[i]} didn't match gold {gold_data[i]} at index {i}"
    else:
        for i in range(len(data_out)):
            if data_out[i] > (1<<16)-1:
                continue
            else:
                assert data_out_p[i] == gold_data_p[i], \
                    f"Output {data_out_p} didn't match gold {gold_data_p[i]} at index {i}"
            



    print(test_name, " passed\n")
    

def test_basic():
    init_module()
    test_list = ["basic_add", "basic_sub", "basic_umult0", "basic_smult0", 
                 "basic_or", "basic_shl", 
                 "basic_abs", 
                 "basic_crop",
                 "basic_urelu",
                 "basic_srelu",
                 'basic_fp_add', 'basic_fp_max',
                 'basic_fp_relu'
                ]


    
    for test in test_list:
        module_iter_basic(test) 
