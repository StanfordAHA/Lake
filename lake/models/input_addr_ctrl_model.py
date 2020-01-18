from lake.models.model import Model
#from lake.models.agg_model import AggModel
from lake.models.addr_gen_model import AddrGenModel
import math as mt
import kratos as kts

class InputAddrCtrlModel(Model):

    def __init__(self, 
               interconnect_input_ports,
               mem_depth,
               banks,
               iterator_support,
               max_port_schedule,
               address_width
    ):

        self.interconnect_input_ports = interconnect_input_ports
        self.mem_depth = mem_depth
        self.banks = banks
        self.iterator_support = iterator_support
        self.address_width = address_width
        self.max_port_schedule = max_port_schedule

        self.config = {}

        # Create child address generators
        self.addr_gens = []
        for i in range(self.interconnect_input_ports):
            new_addr_gen = AddrGenModel(mem_depth=self.mem_depth, 
                                        iterator_support=self.iterator_support,
                                        address_width=self.address_width
                                        )
            self.addr_gens.append(new_addr_gen)

        self.mem_addr_width = kts.clog2(self.mem_depth)

        # Get local list of addresses
        self.addresses = []
        for i in range(self.interconnect_input_ports):
            self.addresses.append(0)

        # Initialize the configuration
        for i in range(self.interconnect_input_ports):
            self.config[f"starting_addr_p_{i}"] = 0
            self.config[f"dimensionality_{i}"] = 0
            for j in range(self.iterator_support):
                self.config[f"stride_p_{i}_{j}"] = 0
                self.config[f"range_p_{i}_{j}"] = 0

        #self.sched_ptrs = []
        #for i in range(self.banks):
        #    self.config[f"port_periods_{i}"] = 0
        #    self.sched_ptrs.append(0)
        #    for j in range(self.max_port_schedule):
        #        self.config[f"port_sched_b_{i}_{j}"] = 0

        # Set up the wen
        self.wen = []
        self.mem_addresses = []
        #self.port_sels = []
        for i in range(self.banks):
            self.wen.append(0)
            self.mem_addresses.append(0)
        #    self.port_sels.append(0)

    def set_config(self, new_config):
        # Configure top level
        for key, config_val in new_config.items():
            if key not in self.config:
                AssertionError("Gave bad config...")
            else:
                self.config[key] = config_val
        # Configure children
        for i in range(self.interconnect_input_ports):
            addr_gen_config = {}
            addr_gen_config["starting_addr"] = self.config[f"starting_addr_p_{i}"]
            addr_gen_config["dimensionality"] = self.config[f"dimensionality_{i}"]
            for j in range(self.iterator_support):
                addr_gen_config[f"range_{j}"] = self.config[f"range_p_{i}_{j}"]
                addr_gen_config[f"stride_{j}"] = self.config[f"stride_p_{i}_{j}"]
            self.addr_gens[i].set_config(addr_gen_config)

    # Retrieve the current addresses from each generator
    def get_addrs(self):
        for i in range(self.interconnect_input_ports):
            to_get = self.addr_gens[i]
            self.addresses[i] = to_get.get_address()
        return self.addresses

    # Get the wen for the current valid input
    def get_wen(self, valid):
        for i in range(self.banks):
            self.wen[i] = 0
        #print(valid)
        for i in range(self.interconnect_input_ports):
            if(valid[i]):
                self.wen[self.get_addrs()[i] >> (self.mem_addr_width)] = 1
                #print(self.get_addrs()[i])
                #print(f"idk:{self.get_addrs()[i] >> (self.mem_addr_width)}")
                #print(f"Setting wen to...{i}")
        return self.wen

    # Step the addresses based on valid
    def step_addrs(self, valid):
        for i, valid_input in enumerate(valid):
            if valid_input:
                #print(f"inserting {in_data} into buffer {self.config[f'in_sched_{self.in_sched_ptr}']}")
                to_step = self.addr_gens[i]
                to_step.step()
        # After stepping the adresses, we need to step the 
        for i in range(self.banks):
            if(valid[self.config[f"port_sched_b_{i}_{self.sched_ptrs[i]}"]]):
                wen[i] = 1

        # Not implemented
    def update_ports(self):
        raise NotImplementedError

    def peek(self):
        raise NotImplementedError
