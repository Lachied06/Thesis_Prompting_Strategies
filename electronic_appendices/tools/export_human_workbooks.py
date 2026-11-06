#!/usr/bin/env python3
"""Export approved workbook cell data, excluding OOXML personal metadata.

Original workbooks are read-only. Supply a private JSON source-ID/path mapping.
Writes only to a new external directory, not the repository. Does not recalculate
formulas or execute macros. Full source hashes and source row numbers are kept.
"""
from pathlib import Path
import argparse,csv,hashlib,json,re
from xlsx_reader import read_workbook,table
ROOT=Path(__file__).resolve().parents[2]
OMIT={'VALIDATION_NEXT_STEPS','THESIS_ACTIONS'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--private-sources',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args();out=a.output_dir.resolve()
 if out==ROOT or ROOT in out.parents:raise ValueError('Output must be external')
 if out.exists() and any(out.iterdir()):raise FileExistsError(out)
 out.mkdir(parents=True,exist_ok=True);records={}
 for source_id,filename in json.loads(a.private_sources.read_text()).items():
  path=Path(filename);workbook=read_workbook(path);meta={'source_id':source_id,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size':path.stat().st_size,'derivation':'OOXML worksheet values only; no document properties, author metadata or filesystem path; no formula evaluation','sheets':{},'omitted_author_handoff_sheets':[]}
  for name,sheet in workbook.items():
   if name in OMIT:meta['omitted_author_handoff_sheets'].append(name);continue
   folder=out/'data'/source_id;folder.mkdir(parents=True,exist_ok=True)
   # Preserve row/cell addresses and all original text, including protocol notes.
   grid=folder/(name+'.cells.json');grid.write_text(json.dumps(sheet,ensure_ascii=False,indent=2)+'\n')
   rows=table(sheet)
   if rows:
    with (folder/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
     w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
   meta['sheets'][name]={'ooxml_member':sheet['member'],'rows':len(sheet['rows']),'table_rows_after_row_4':len(rows),'cells_path':grid.relative_to(out).as_posix()}
  records[source_id]=meta
 (out/'source_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
 print('Exported',len(records),'workbook sources; originals unchanged; metadata omitted.')
if __name__=='__main__':main()
