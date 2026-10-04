"""Rellena índice, índice de figuras y de tablas con LibreOffice (sin que Word pida actualizar campos).

Uso:  python3 memoria/actualizar_indices.py memoria/TFM_StrokeLab_borrador.docx memoria/TFM_StrokeLab_final.docx
"""
import subprocess, time, sys, uno
from com.sun.star.beans import PropertyValue
src, dst = sys.argv[1], sys.argv[2]
p = subprocess.Popen(['soffice', '--headless', '--invisible', '--norestore',
                      '--accept=socket,host=localhost,port=2002;urp;'])
ctx = uno.getComponentContext()
res = ctx.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', ctx)
for _ in range(60):
    try:
        c = res.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext'); break
    except Exception: time.sleep(1)
desk = c.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', c)
def pv(n, v):
    x = PropertyValue(); x.Name, x.Value = n, v; return x
doc = desk.loadComponentFromURL(uno.systemPathToFileUrl(src), '_blank', 0, (pv('Hidden', True),))
doc.getTextFields().refresh()
idx = doc.getDocumentIndexes()
print('indices:', idx.getCount())
for i in range(idx.getCount()):
    ix = idx.getByIndex(i); ix.update(); print(' ', ix.getImplementationName(), getattr(ix, 'LabelCategory', ''))
doc.getTextFields().refresh()
doc.storeToURL(uno.systemPathToFileUrl(dst), (pv('FilterName', 'MS Word 2007 XML'),))
doc.close(True)
try: desk.terminate()
except Exception: pass
p.wait(timeout=30)
