from lake.models.model import Model


class RegisterFileModel(Model):
    def __init__(self,
                 data_width,
                 write_ports,
                 read_ports,
                 width_mult,
                 depth):

        self.width_mult = width_mult
        self.data_width = data_width
        self.write_ports = write_ports
        self.read_ports = read_ports
        self.depth = depth

        self.mem = []
        for i in range(self.depth):
            row = []
            for j in range(self.width_mult):
                row.append(0)
            self.mem.append(row)

    def set_config(self, new_config):
        # No configuration space
        return

    def interact(self,
                 wen,
                 wr_addr,
                 rd_addr,
                 data_in):
        '''
        Returns rd_data (list)
        '''

        # Do the read first - data won't pass through on the same cycle
        ret_data = []
        if self.read_ports == 1:
            ret_data.append(self.mem[rd_addr].copy())
        else:
            for i in range(self.read_ports):
                ret_data.append(self.mem[rd_addr[i]].copy())

        if self.write_ports == 1:
            if wen:
                self.mem[wr_addr] = data_in.copy()
        else:
            for i in range(self.write_ports):
                if wen[i] == 1:
                    self.mem[wr_addr[i]] = data_in[i].copy()

        return ret_data.copy()

    def get_reads(self, rd_addr):
        ret_data = []
        if self.read_ports == 1:
            ret_data.append(self.mem[rd_addr].copy())
        else:
            for i in range(self.read_ports):
                ret_data.append(self.mem[rd_addr[i]].copy())

    def dump_mem(self):
        for i in range(self.depth):
            print(f"addr: {i}, data: {self.mem[i]}")
