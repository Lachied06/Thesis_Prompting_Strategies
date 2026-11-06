"""Prepared 6 November 2026 for explicit local reconstruction, not historical code.

Requires a lawfully obtained frozen SciFact corpus. Writes a new external folder;
never replaces shipped or private experimental files and never calls a model.
"""
from pathlib import Path
import argparse, hashlib, json, importlib.util

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    out=a.output_dir.resolve()
    if out==root or root in out.parents or out.exists():
        raise ValueError('Choose a NEW directory outside this repository')
    recipes=json.loads((Path(__file__).parent/'scifact_task_recipes.json').read_text())
    raw=a.corpus.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=recipes['corpus_sha256']:
        raise ValueError('Corpus differs from frozen bytes; reconstruction refused')
    corpus={str(r['doc_id']):r for r in map(json.loads,raw.decode().splitlines()) if r}
    spec=importlib.util.spec_from_file_location('frozen_task_preparation',root/'prepare_benchmarks.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    pending=[]
    for file in recipes['files']:
        rows=[]
        for recipe in file['records']:
            r=dict(recipe['record_without_source_context'])
            r['source_context']=module._format_source_context(recipe['ordered_corpus_ids'],corpus) or None
            rows.append(r)
        data=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows).encode()
        if hashlib.sha256(data).hexdigest()!=file['sha256']:
            raise ValueError('Frozen task hash mismatch: '+file['path'])
        pending.append((file['path'],data))
    out.mkdir(parents=True)
    for name,data in pending:
        f=out/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
    (out/'RECONSTRUCTION_NOTICE.txt').write_text(
        'NEW LOCAL RECONSTRUCTION, 2026-11-06 helper. All ten task-file hashes match '
        'the frozen archive. This does not recreate model outputs or establish public '
        'redistribution rights. Original private records remain authoritative.\n')
    print('10 reconstructed task files match frozen SHA-256 values:',out)

if __name__=='__main__':main()
