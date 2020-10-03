import kratos as kts
from enum import Enum
from enum import auto


class FormalSignalConstraint(Enum):
    X = auto()
    SET0 = auto()
    SET1 = auto()
    CLK = auto()
    RSTN = auto()
    SOLVE = auto()
    SEQUENCE = auto()


class FormalAttr(kts.Attribute):
    def __init__(self,
                 port_name,
                 formalsig_cnst,
                 doc_string=""):
        super().__init__()
        self.port_name = port_name
        self.formalsig_cnst = formalsig_cnst
        self.documentation = doc_string
        self.annotation = f"{self.port_name}\t{self.formalsig_cnst.name}"

    def set_documentation(self, new_doc):
        self.documentation = new_doc

    def get_documentation(self):
        return self.documentation

    def get_annotation(self):
        return self.annotation

    def get_port_name(self):
        return self.port_name

    def get_formal_ann(self):
        return self.formalsig_cnst
