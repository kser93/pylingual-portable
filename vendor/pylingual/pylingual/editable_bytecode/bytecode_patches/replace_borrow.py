from ..EditableBytecode import EditableBytecode

def replace_borrow(bytecode: EditableBytecode):
    if bytecode.version < (3,14):
        return
    load_fast_borrows = [inst for inst  in bytecode.instructions if inst.opname == "LOAD_FAST_BORROW"]
    for borrow in load_fast_borrows:
        borrow.opname = "LOAD_FAST"
        borrow.opcode = bytecode.opcode.LOAD_FAST

    double_load_fast_borrows = [inst for inst  in bytecode.instructions if inst.opname == "LOAD_FAST_BORROW_LOAD_FAST_BORROW"]
    for double_borrow in double_load_fast_borrows:
        double_borrow.opname = "LOAD_FAST_LOAD_FAST"
        double_borrow.opcode = bytecode.opcode.LOAD_FAST_LOAD_FAST
