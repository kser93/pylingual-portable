from ..EditableBytecode import EditableBytecode

import itertools


def replace_firstlno(bytecode: EditableBytecode):
    to_replace = next(
        (load_const for load_const, store_name in itertools.pairwise(bytecode.instructions) if load_const.opname in ["LOAD_CONST", "LOAD_SMALL_INT"] and store_name.opname == "STORE_NAME" and store_name.argval == "__firstlineno__"), None
    )
    if to_replace is not None:
        to_replace.argval = 0
        to_replace.argrepr = "0"

        if bytecode.version >= (3, 14):
            to_replace.opname = "LOAD_SMALL_INT"
            to_replace.opcode = bytecode.opcode.LOAD_SMALL_INT
            to_replace.optype = "??"
