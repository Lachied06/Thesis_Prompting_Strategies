#!/usr/bin/env python3
"""Deterministic external ZIP with one Code/ tree; never modifies the checkout.

Public redistribution rights must be resolved by the author. --list-only needs
no acknowledgment and writes no archive. No Git operations or network access.
"""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[2]

def included(root):
 return sorted(p for p in root.rglob('*') if p.is_file() and not p.is_symlink() and not any(x in {'.git','.venv','__pycache__','.pytest_cache'} for x in p.relative_to(root).parts) and p.name not in {'.env','.DS_Store'})

def create_zip(root,files,destination):
 destination=Path(destination)
 if destination.exists():raise FileExistsError(destination)
 with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
  index=[]
  for p in files:
   data=p.read_bytes();name='Code/'+p.relative_to(root).as_posix();entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;archive.writestr(entry,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9);index.append({'path':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
  entry=zipfile.ZipInfo('DELIVERY_CONTENTS.json',date_time=(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;archive.writestr(entry,json.dumps(index,indent=2)+'\n',compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 with zipfile.ZipFile(destination) as archive:
  assert archive.testzip() is None
  for record in index:assert hashlib.sha256(archive.read(record['path'])).hexdigest()==record['sha256']
 return index

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);p.add_argument('--list-only',action='store_true');p.add_argument('--acknowledge-data-rights',action='store_true',help='Author acknowledges distribution-rights decision; not a licence grant');a=p.parse_args();files=included(ROOT)
 if a.list_only:print(json.dumps([x.relative_to(ROOT).as_posix() for x in files],indent=2));return
 if not a.output or not a.acknowledge_data_rights:p.error('An external --output and explicit --acknowledge-data-rights are required; resolve rights before delivery')
 out=a.output.resolve()
 if out==ROOT or ROOT in out.parents:p.error('ZIP must be outside the repository')
 index=create_zip(ROOT,files,out);print('Verified external ZIP:',out,'files:',len(index))
if __name__=='__main__':main()
