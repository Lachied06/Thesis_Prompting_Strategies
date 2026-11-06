#!/usr/bin/env python3
"""Read-only consistency checks of exported human-review stages and saved labels.

No resampling, label changes, model calls or new inference. Output may be stdout
or an explicitly external JSON path. Original worksheets remain authoritative.
"""
from pathlib import Path
import argparse,csv,json,collections,math
ROOT=Path(__file__).resolve().parents[2]
G=ROOT/'electronic_appendices/G_Human_Audit'

def read(source,sheet):
 with (G/'data'/source/(sheet+'.csv')).open(newline='') as f:return list(csv.DictReader(f))
def metric(rows,field,rule):
 tp=fp=tn=fn=0
 for r in rows:
  human=r[field]
  if human=='Cannot assess':continue
  if human not in {'Supported','Unsupported','Contradicted'}:raise ValueError(human)
  y=human in {'Unsupported','Contradicted'};p=r['Primary support'] in {'CONTRADICTED','NOT_IN_SOURCES'};q=r['Secondary support'] in {'CONTRADICTED','NOT_IN_SOURCES'}
  pred={'strict':p and q,'primary':p,'secondary':q,'either':p or q}[rule]
  if y and pred:tp+=1
  elif pred:fp+=1
  elif y:fn+=1
  else:tn+=1
 n=tp+fp+tn+fn;observed=(tp+tn)/n;expected=((tp+fp)*(tp+fn)+(tn+fn)*(tn+fp))/(n*n)
 return {'TP':tp,'FP':fp,'TN':tn,'FN':fn,'Evaluable N':n,'Agreement':observed,'Precision':tp/(tp+fp) if tp+fp else None,'Recall':tp/(tp+fn) if tp+fn else None,'Specificity':tn/(tn+fp) if tn+fp else None,"Cohen's κ":(observed-expected)/(1-expected) if expected!=1 else None,'Human positives':tp+fn}

def check():
 key=read('selection_key','SAMPLE_KEY');joined=read('final_comparison','ALL_433_CLAIMS');initial=read('initial_review','CLAIM_ANNOTATIONS');final=read('adjudicated_review','CLAIM_ANNOTATIONS');rep=read('repeat_completed','REPEAT_CLAIMS');saved=read('final_comparison','AGREEMENT_METRICS');bykey={r['Blind ID']:r for r in key};bi={r['Full Claim ID']:r for r in initial};bf={r['Full Claim ID']:r for r in final}
 assert len(key)==40 and len({r['Run ID'] for r in key})==40
 assert len(joined)==len(initial)==len(final)==433 and set(bi)==set(bf)=={r['Full Claim ID'] for r in joined}
 random=[r for r in joined if r['Stream']=='Random paired'];randomkey=[r for r in key if r['Selection stream']=='Random paired']
 cells=collections.defaultdict(set)
 for r in randomkey:cells[(r['Generating model'],r['Difficulty stratum'],r['Task ID'])].add(r['Prompt strategy'])
 assert len(randomkey)==32 and len(cells)==8 and all(s=={'baseline','structured','source_grounded','chain_of_verification'} for s in cells.values())
 assert all(r['Final human label']==bf[r['Full Claim ID']]['Human support label'] for r in joined)
 consensus={c['claim_id']:c for line in (ROOT/'outputs/scifact_confirmatory_v3_2/atomic_consensus_v3_9/atomic_consensus.jsonl').open() for r in [json.loads(line)] for c in r['claims']}
 assert all(r['Primary support']==consensus[r['Full Claim ID']]['primary_support_status'] and r['Secondary support']==consensus[r['Full Claim ID']]['secondary_support_status'] for r in joined)
 scenarios=[('Pre-adjudication reference',random,'Archived human label'),('Final adjudicated reference',random,'Final human label'),('Extraction-aware sensitivity (6 invalid claims excluded)',[r for r in random if r['Potential extraction invalid?']!='Confirmed extraction distortion'],'Final human label')]
 checks=[]
 for scenario,rows,field in scenarios:
  for rule in ['strict','primary','secondary','either']:
   actual=metric(rows,field,rule);s=next(r for r in saved if r['Scenario']==scenario and r['Automated rule']==rule)
   assert all(math.isclose(float(s[k]),v,rel_tol=1e-12,abs_tol=1e-12) for k,v in actual.items() if v is not None),(scenario,rule,actual,s)
   checks.append({'scenario':scenario,'rule':rule,'status':'PASS','recomputed':actual,'saved_source_row':s['source_row']})
 repeat_matches=sum(bi[r['Full Claim ID (do not edit)']]['Human support label']==r['SECOND-PASS support label'] for r in rep)
 assert len(rep)==48 and repeat_matches==44
 archived_differences=[{'claim_id':r['Full Claim ID'],'blind_id':r['Blind ID'],'claim_number':r['Claim #'],'initial_workbook_label':bi[r['Full Claim ID']]['Human support label'],'comparison_archived_label':r['Archived human label']} for r in joined if r['Archived human label']!=bi[r['Full Claim ID']]['Human support label']]
 assert len(archived_differences)==6
 # Check saved four-rule point estimates only; do not generate bootstrap intervals.
 grouped=collections.defaultdict(lambda:collections.defaultdict(list))
 for line in (ROOT/'outputs/scifact_confirmatory_v3_2/atomic_consensus_v3_9/atomic_consensus.jsonl').open():
     rec=json.loads(line);sub=rec['subject'];ev=[c for c in rec['claims'] if c['support_consensus']!='EXCLUDED_NOT_FACTUAL'];n=len(ev)
     flags={'consensus':sum(c['support_consensus']=='CONSENSUS_UNSUPPORTED' for c in ev),'primary':sum(c['primary_support_status'] in {'CONTRADICTED','NOT_IN_SOURCES'} for c in ev),'secondary':sum(c['secondary_support_status'] in {'CONTRADICTED','NOT_IN_SOURCES'} for c in ev),'either':sum(bool(c['possible_unsupported']) for c in ev)}
     for rule,value in flags.items():grouped[(sub['model']['name'],sub['strategy']['name'])][rule].append(value/n)
 means={key:{rule:100*sum(values)/len(values) for rule,values in byrule.items()} for key,byrule in grouped.items()}
 for r in read('final_comparison','FULL_800_SENSITIVITY'):
     if r.get('Model') not in {key[0] for key in means}:continue
     for rule,label in [('consensus','Consensus'),('primary','Primary'),('secondary','Secondary'),('either','Either')]:
         expected=means[(r['Model'],r['Strategy'])][rule]
         assert math.isclose(float(r[label+' rate %']),expected,abs_tol=1e-10)
         assert math.isclose(float(r[label+' Δ pp']),expected-means[(r['Model'],'baseline')][rule],abs_tol=1e-10)
 for r in read('final_comparison','PAIRED_BOOTSTRAP_CI'):
     if r.get('Model') not in {key[0] for key in means}:continue
     expected=means[(r['Model'],r['Strategy'])][r['Judge rule']]-means[(r['Model'],'baseline')][r['Judge rule']]
     assert math.isclose(float(r['Paired Δ pp']),expected,abs_tol=1e-10)
 assert dict(collections.Counter(r['Human support label'] for r in final))=={'Supported':411,'Unsupported':19,'Cannot assess':3}
 assert metric(random,'Final human label','strict')['TP']==2 and len(random)==313
 return {'full_800_four_rule_point_estimates_match_saved':True,'scope':'Read-only reproduction of saved human-audit consistency metrics; no new inferential analysis or label corrections','status':'PASS','responses':40,'claims':433,'random_responses':32,'random_claims':313,'purposive_responses':8,'purposive_claims':120,'initial_workbook_labels':dict(collections.Counter(r['Human support label'] for r in initial)),'comparison_archived_reference_labels':dict(collections.Counter(r['Archived human label'] for r in joined)),'final_labels':dict(collections.Counter(r['Human support label'] for r in final)),'comparison_archived_is_not_identical_to_initial_workbook':archived_differences,'repeat_claims':48,'initial_vs_repeat_matches':repeat_matches,'repeat_labels':dict(collections.Counter(r['SECOND-PASS support label'] for r in rep)),'all_12_saved_metric_rows_reproduced':checks,'unverified':['Actual reviewer compliance with blinding and elapsed repeat interval cannot be independently established from workbooks.','Original sampling/workbook generation code not located.','Saved 5000-resample sensitivity intervals are preserved, not newly generated or claimed exactly reproduced.']}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args();result=check();text=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
 if a.output:
  out=a.output.resolve()
  if out==ROOT or ROOT in out.parents:raise ValueError('Log output must be external')
  if out.exists():raise FileExistsError(out)
  out.write_text(text)
 else:print(text,end='')
