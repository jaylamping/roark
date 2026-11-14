import pythoncom, sys
tl = pythoncom.LoadTypeLib(sys.argv[1])
pat = [p.lower() for p in sys.argv[2:]]
for i in range(tl.GetTypeInfoCount()):
    name = tl.GetDocumentation(i)[0]
    if not any(p in name.lower() for p in pat): continue
    ti = tl.GetTypeInfo(i); attr = ti.GetTypeAttr()
    print("==", name)
    for j in range(attr.cFuncs):
        fd = ti.GetFuncDesc(j); names = ti.GetNames(fd.memid)
        kind = {2:"get",4:"put",8:"putref",1:""}.get(fd.invkind, str(fd.invkind))
        print("  ", kind, names[0], "(", ", ".join(names[1:]), ")")
