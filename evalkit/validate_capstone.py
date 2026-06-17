#!/usr/bin/env python3
"""Independent re-derivation of CEIL to validate it is not an artifact of the
objdump/nm text extractor. This pipeline parses the ELF objects with pyelftools
(symbols, sections, relocations) and disassembles with Capstone, then applies the
SAME identifiability gate, imported from bin_features. Only the disassembly and ELF
parsing differ; the rules (rare-constant test, magic catalogue, libc filter,
rodata/jump-table handling) are shared. Agreement with the objdump extractor shows
the ceiling is a property of the binaries, not of how we read objdump's output.
"""
import os, glob, statistics
from capstone import (Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_IMM, CS_OP_MEM, CS_OP_REG,
                      CS_GRP_JUMP, CS_GRP_CALL)
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
import bin_features as bf

OPT = {'zlib-O0', 'zlib-O3', 'zlib-Os'}
RODATA = ('.rodata', '.data.rel.ro')
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True

def text_defined(elf, text_idx):
    """Function names defined in a text section of this object (mirror of nm T/t)."""
    d = set()
    for sym in elf.get_section_by_name('.symtab').iter_symbols():
        if sym['st_info']['type'] == 'STT_FUNC' and isinstance(sym['st_shndx'], int) \
           and sym['st_shndx'] in text_idx and sym.name:
            d.add(sym.name)
    return d

def library_defined(objs):
    """Union of text-defined function names across all objects in the library, so a
    cross-object intra-library call is recognized as internal (matches nm over the
    whole library, as the objdump extractor does)."""
    alld = set()
    for o in objs:
        with open(o, 'rb') as fh:
            elf = ELFFile(fh)
            tin = {i for i, s in enumerate(elf.iter_sections())
                   if s['sh_type'] == 'SHT_PROGBITS' and (s['sh_flags'] & 0x4)}
            alld |= text_defined(elf, tin)
    return alld

def ceil_capstone(obj, lib_defined, T=4096, filter_libc=True):
    with open(obj, 'rb') as fh:
        elf = ELFFile(fh)
        syms = list(elf.get_section_by_name('.symtab').iter_symbols())
        secname = {i: s.name for i, s in enumerate(elf.iter_sections())}
        text_idx = {i for i, s in enumerate(elf.iter_sections())
                    if s['sh_type'] == 'SHT_PROGBITS' and (s['sh_flags'] & 0x4)}
        # name -> defining section (mirror of objdump -t), and the set of defined funcs
        sym_sec = {}
        defined = set()
        funcs = []
        for sym in syms:
            shndx = sym['st_shndx']
            if sym.name and isinstance(shndx, int):
                sym_sec[sym.name] = secname.get(shndx, '')
            if sym['st_info']['type'] == 'STT_FUNC' and isinstance(shndx, int) and shndx in text_idx:
                defined.add(sym.name)
                funcs.append([sym.name, shndx, sym['st_value'], sym['st_size']])
        # zero-size functions: extend to the next function symbol in the same section
        bysec = {}
        for f in funcs:
            bysec.setdefault(f[1], []).append(f)
        for shndx, fl in bysec.items():
            fl.sort(key=lambda f: f[2])
            seclen = len(elf.get_section(shndx).data())
            for j, f in enumerate(fl):
                if f[3] == 0:
                    f[3] = (fl[j + 1][2] if j + 1 < len(fl) else seclen) - f[2]
        # relocations grouped by the text section they apply to
        relocs = {}
        for s in elf.iter_sections():
            if isinstance(s, RelocationSection) and s['sh_info'] in text_idx:
                lst = relocs.setdefault(s['sh_info'], [])
                for r in s.iter_relocations():
                    lst.append((r['r_offset'], r['r_info_sym'], r['r_addend']))

        N = searchable = 0
        for name, shndx, value, size in funcs:
            N += 1
            data = elf.get_section(shndx).data()
            body = data[value:value + size]
            insns = list(md.disasm(body, value)) if body else []
            has_const = has_str = has_named = ext = False
            anon = ind_jmps = 0
            for ins in insns:
                if not (set(ins.groups) & {CS_GRP_JUMP, CS_GRP_CALL}):  # branch targets are IMM; skip
                    for op in ins.operands:
                        # Capstone returns imm as a signed int64; the objdump path reads the
                        # hex text at the operand width. Normalize to the unsigned value of that
                        # width so the two agree: a sign-extended imm8 in a 32-bit compare reads
                        # 0xfffffffb (large) as objdump shows it, not -5; a 64-bit hash prime with
                        # bit 63 set keeps its unsigned form and so still hits the magic catalogue.
                        if op.type == CS_OP_IMM:
                            width = op.size or 8
                            v = op.imm & ((1 << (width * 8)) - 1)
                            if bf.is_rare_constant(v, T):
                                has_const = True
                # Indirect jump through a register (jmp *%reg, and notrack jmp *%reg): the
                # .rodata reloc on the table-base load is a jump table, not a distinctive
                # data reference, so discount one anon. Detect via the jump group, not the
                # mnemonic: Capstone folds the CET notrack prefix into the mnemonic string
                # ("notrack jmp"), which a startswith('jmp') test silently misses.
                if (CS_GRP_JUMP in ins.groups) and ins.operands and \
                   ins.operands[0].type == CS_OP_REG:
                    ind_jmps += 1
            for off, symidx, addend in relocs.get(shndx, []):
                if not (value <= off < value + size):
                    continue
                sym = syms[symidx]
                is_section = (sym['st_info']['type'] == 'STT_SECTION' or not sym.name)
                base = secname.get(sym['st_shndx'], '') if is_section else sym.name
                ins_at = next((i for i in insns if i.address <= off < i.address + i.size), None)
                is_call = bool(ins_at and ins_at.mnemonic.startswith(('call', 'jmp')))
                if base.startswith('.rodata.str'):
                    has_str = True
                elif base.startswith('.rodata.cst'):
                    pass
                elif (not base.startswith('.')) and base in sym_sec and sym_sec[base].startswith(RODATA):
                    has_named = True
                elif base.startswith('.rodata'):
                    anon += 1
                elif base.startswith('.data.rel.ro'):
                    pass
                elif is_call and not base.startswith('.') and base not in lib_defined:
                    if not (filter_libc and base in bf.LIBC_COMMON):
                        ext = True
            anon = max(0, anon - ind_jmps)
            if has_const or has_str or has_named or anon > 0 or ext:
                searchable += 1
        return (100.0 * searchable / N if N else 0.0, N)

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    libs = [d for d in sorted(glob.glob(os.path.join(base, 'corpus', '*', 'obj')))
            if os.path.basename(os.path.dirname(d)) not in OPT]
    print(f"{'library':14s} {'objdump CEIL':>13s} {'capstone CEIL':>14s} {'N(obj/cap)':>12s}")
    print('-' * 56)
    diffs = []
    for d in libs:
        lib = os.path.basename(os.path.dirname(d))
        ro = bf.measure_library(d)
        objs = sorted(glob.glob(os.path.join(d, '*.o')))
        lib_defined = library_defined(objs)
        sc = 0; n = 0
        for o in objs:
            c, k = ceil_capstone(o, lib_defined)
            sc += c * k / 100.0; n += k
        cap = 100.0 * sc / n if n else 0.0
        diffs.append(abs(ro['ceil'] - cap))
        print(f"{lib:14s} {ro['ceil']:12.1f}% {cap:13.1f}% {ro['N']:6d}/{n:<5d}")
    print('-' * 56)
    print(f"mean |objdump - capstone| = {statistics.mean(diffs):.2f} points; "
          f"max = {max(diffs):.2f}")

if __name__ == '__main__':
    main()
