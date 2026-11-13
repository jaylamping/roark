import pythoncom, sys
tl = pythoncom.LoadTypeLib(sys.argv[1])
want = set(sys.argv[2:])
for i in range(tl.GetTypeInfoCount()):
    n = tl.GetDocumentation(i)[0]
    if n in want:
        ti = tl.GetTypeInfo(i); a = ti.GetTypeAttr()
        print(n, {ti.GetNames(ti.GetVarDesc(j).memid)[0]: ti.GetVarDesc(j).value for j in range(a.cVars)})
