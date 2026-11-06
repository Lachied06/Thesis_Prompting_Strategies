#!/usr/bin/env python3
"""Read-only appendix and frozen-evidence validation; no network/APIs/inference.

Optional log output and baseline inventory must be outside the repository.
NOT VERIFIED statuses are preserved; success does not certify open items.
"""
from pathlib import Path
import argparse,csv,hashlib,json,re,tempfile,zipfile,importlib.util
from export_evidence import export,ROOT
from check_human_audit import check as check_human
EA=ROOT/'electronic_appendices'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(skip=False,baseline=None):
 rows=[]
 def add(name,passed,evidence,status=None):rows.append({'check':name,'status':status or ('PASS' if passed else 'FAIL'),'evidence':evidence})
 # Reproduce every canonical export into an independent temporary directory.
 with tempfile.TemporaryDirectory(prefix='thesis_appendix_export_check_') as temp:
  export(temp)
  for p in Path(temp).rglob('*'):
   if p.is_file():add('Export equality: '+p.relative_to(temp).as_posix(),(EA/p.relative_to(temp)).read_bytes()==p.read_bytes(),'Original canonical sources; external temporary recomputation')
 errors=[]
 for p in EA.rglob('*'):
  if not p.is_file():continue
  try:
   if p.suffix=='.json':json.loads(p.read_text())
   elif p.suffix=='.jsonl':
    with p.open() as f:
     for line in f:
      if line.strip():json.loads(line)
   elif p.suffix=='.csv':
    with p.open(newline='') as f:list(csv.reader(f))
   elif p.suffix in {'.md','.txt','.py'}:p.read_text()
   elif p.suffix=='.png':assert p.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
  except Exception as e:errors.append(str(p.relative_to(ROOT))+': '+str(e))
 add('All added structured/text/image files readable',not errors,errors)
 missing=[]
 for p in EA.rglob('*.md'):
  text=re.sub(r'```.*?```','',p.read_text(),flags=re.S)
  for link in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)',text):
   if re.match(r'\w+://',link):continue
   target=(p.parent/link.split('#',1)[0]).resolve()
   if not target.is_relative_to(ROOT) or not target.exists():missing.append([p.relative_to(ROOT).as_posix(),link])
 add('Portable appendix-relative Markdown links',not missing,missing)
 figures=json.loads((EA/'D_Results/figure_provenance.json').read_text())
 add('Manuscript image bytes match provenance',all(sha(EA/'D_Results'/r['path'])==r['sha256'] for r in figures['records']),'Exact embedded images, not regenerated')
 means=list(csv.DictReader((EA/'D_Results/evidence_condition_means.csv').open()))
 observed={'gpt-5.4-mini':[[6.7,6.2,6.8,4.0],[5.5,3.6,2.8,4.0],[2.9,3.8,1.7,3.9],[1.7,1.1,.7,.7]],'gpt-5.5':[[5.0,4.5,3.2,5.0],[3.2,.3,2.8,4.9],[1.4,1.0,.4,1.6],[1.8,.9,0.0,3.8]]}
 figmatches=[]
 for model,data in observed.items():
  for strategy,values in zip(['baseline','structured','source_grounded','chain_of_verification'],data):
   for difficulty,number in zip(['direct_control','near_match_distractors','evidence_omission','conflicting_or_partial_evidence'],values):
    r=next(r for r in means if model in r['condition'] and ('| '+strategy+'@') in r['condition'] and r['difficulty']==difficulty);figmatches.append(f"{float(r['mean_response_consensus_unsupported_claim_rate'])*100:.1f}"==f'{number:.1f}')
 add('Figure D2 displayed values match 32 stored means',all(figmatches),'Observed manuscript image text compared to stored summary at displayed precision')
 h=check_human();add('Human-review counts and all 12 saved comparison rows',h['status']=='PASS','Separate stage extracts; no labels changed or cases resampled')
 # Whole-workbook source cell hashes are external; approved derivative hashes are in root inventory.
 recovered=json.loads((EA/'F_Pilots/recovered_provenance.json').read_text())
 add('Recovered HaluEval member hashes',all(sha(EA/r['path'])==r['source_sha256'] for r in recovered['records']),'Byte-identical archive members')
 pilot=[json.loads(l) for l in (EA/'F_Pilots/recovered_halueval/results.jsonl').open() if l.strip()]
 add('56 completed HaluEval responses / 84 generation steps',len(pilot)==56 and all(r['status']=='completed' for r in pilot) and sum(len(r['trace']) for r in pilot)==84,'Historical pilot outside final 800')
 # New packager round-trip is tested on a synthetic external fixture only.
 from package_appendices import create_zip
 with tempfile.TemporaryDirectory(prefix='thesis_packaging_fixture_') as temp:
  t=Path(temp);fixture=t/'fixture';fixture.mkdir();(fixture/'example.txt').write_text('Synthetic packaging test; no research data.\n');a=t/'one.zip';b=t/'two.zip';create_zip(fixture,[fixture/'example.txt'],a);create_zip(fixture,[fixture/'example.txt'],b);add('Packaging tool synthetic deterministic round-trip',a.read_bytes()==b.read_bytes(),'No real research ZIP generated or redistributed')
 index=EA/'E_Reproducibility/authoritative_file_manifest.csv'
 if index.exists():
  entries=list(csv.DictReader(index.open()));add('Supplementary file index hashes/sizes',all((ROOT/r['path']).exists() and (not r['sha256'] or sha(ROOT/r['path'])==r['sha256']) and (not r['size'] or (ROOT/r['path']).stat().st_size==int(r['size'])) for r in entries),'Dynamic integrity files/self rows deliberately omit hashes')
 else:add('Supplementary file index',False,'Not yet generated')
 if baseline:
  b=json.loads(baseline.read_text());bad=[n for n,r in b.items() if n not in {'PACKAGE_MANIFEST.json','SHA256SUMS.txt'} and (not (ROOT/n).exists() or sha(ROOT/n)!=r['sha256'])];add('All pre-existing protected hashes unchanged',not bad,bad)
 if not skip:
  listed={n:d for d,n in (l.split('  ',1) for l in (ROOT/'SHA256SUMS.txt').read_text().splitlines())};actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not p.is_symlink()};add('Root checksum inventory complete and correct',actual==set(listed)|{'SHA256SUMS.txt'} and all((ROOT/n).exists() and sha(ROOT/n)==d for n,d in listed.items()),'SHA256SUMS.txt excludes itself')
 for name,evidence in [('Original sampling/figure-generation code','Not located; workbook procedure and exact embedded images are retained'),('Historical numbered checks 1–19','Unlocated; current checks are EA-prefixed'),('Actual review blinding/timing compliance','Instructions support intended protocol; behavior not independently evidenced'),('Original 5000-resample sensitivity interval reproduction','Saved worksheet values retained; original bootstrap code absent'),('Dataset/public-release permissions','Unverified; no publication or real submission ZIP performed'),('HaluEval dual-judge atomic records','Not found in inspected source archives')]:add(name,False,evidence,'NOT VERIFIED')
 return {'status':'FAIL' if any(r['status']=='FAIL' for r in rows) else 'APPENDICES PARTIALLY ASSEMBLED — OPEN ITEMS','checks':rows,'human_audit_summary':h}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skip-package-integrity',action='store_true');p.add_argument('--baseline',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();r=validate(a.skip_package_integrity,a.baseline);text=json.dumps(r,ensure_ascii=False,indent=2)+'\n'
 if a.output:
  out=a.output.resolve()
  if out==ROOT or ROOT in out.parents:raise ValueError('Logs must be external')
  if out.exists():raise FileExistsError(out)
  out.write_text(text)
 else:print(text,end='')
 raise SystemExit(1 if r['status']=='FAIL' else 0)
