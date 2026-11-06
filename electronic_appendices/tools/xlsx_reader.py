import zipfile,xml.etree.ElementTree as ET,posixpath,re
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def read_workbook(path):
 with zipfile.ZipFile(path) as z:
  strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)] if 'xl/sharedStrings.xml' in z.namelist() else []
  rels={e.get('Id'):e.get('Target') for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
  result={}
  for s in ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet',NS):
   target=rels[s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')];member=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
   rows=[]
   for r in ET.fromstring(z.read(member)).findall('m:sheetData/m:row',NS):
    cells={}
    for c in r.findall('m:c',NS):
     v=c.find('m:v',NS);text=v.text if v is not None else ''.join(e.text or '' for e in c.findall('m:is//m:t',NS));text=strings[int(text)] if c.get('t')=='s' else text
     cells[c.get('r')]=text or ''
    rows.append({'row':int(r.get('r')),'cells':cells})
   result[s.get('name')]={'member':member,'rows':rows}
  return result

def table(sheet,header_row=4):
 rows=sheet['rows'];header=next((r for r in rows if r['row']==header_row),None)
 if not header:return []
 cols={re.sub(r'\d','',cell):value for cell,value in header['cells'].items() if value}
 return [{'source_row':r['row'],**{v:r['cells'].get(k+str(r['row']),'') for k,v in cols.items()}} for r in rows if r['row']>header_row and any(r['cells'].values())]
