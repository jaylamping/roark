import pythoncom, sys
tl = pythoncom.LoadTypeLib(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\sldworks.tlb")
want = sys.argv[1:]
for i in range(tl.GetTypeInfoCount()):
    ti = tl.GetTypeInfo(i)
    name = tl.GetDocumentation(i)[0]
    attr = ti.GetTypeAttr()
    for j in range(attr.cFuncs):
        fd = ti.GetFuncDesc(j)
        names = ti.GetNames(fd.memid)
        if f"{name}.{names[0]}" in want:
            print(name, names[0], "(", ", ".join(names[1:]), ")")
