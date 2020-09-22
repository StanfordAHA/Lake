from kratos import *
import json


def get_memory_params(memory, mem_collateral):
    orig_gen = Generator("original")
    mem_dict = vars(memory).copy()

    mem_dict = dict((key, value) for key, value in memory.__dict__.items() 
                if not callable(value) and not key.startswith('__'))
    for key in vars(orig_gen):
        if key in mem_dict:
            del mem_dict[key]

    mem_idx = len(mem_collateral)

    mem_collateral[f"mem_{mem_idx}"] = mem_dict


def get_json(mem_collateral): # will also include edge collateral to form Lake object

    with open ('collateral2compiler.json', 'w') as outfile:
        json.dump(mem_collateral, outfile, indent=4)
