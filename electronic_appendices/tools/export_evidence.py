#!/usr/bin/env python3
"""Export existing evidence to a NEW EXTERNAL directory; no APIs or new inference."""
from __future__ import annotations
import argparse, csv, hashlib, json, sys, collections, statistics
from dataclasses import asdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.prompting import PROMPT_REGISTRY, SYNTHESIS_STRESS_OUTPUT_CONTRACT

STUDY = 'outputs/scifact_confirmatory_v3_2'
TASKS = 'data/approved/scifact_confirmatory_100.jsonl'
RESULTS = STUDY + '/results.jsonl'
CONSENSUS = STUDY + '/atomic_consensus_v3_9/atomic_consensus.jsonl'
SUMMARY = STUDY + '/atomic_consensus_v3_9/atomic_consensus_summary.json'
STRATEGIES = ('baseline','structured','source_grounded','chain_of_verification')

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads((ROOT/path).read_text())
def lines(path):
    with (ROOT/path).open() as f:
        return [json.loads(line) for line in f if line.strip()]

def export(out):
    out = Path(out).resolve()
    if out == ROOT or ROOT in out.parents: raise ValueError('Output must be outside repository')
    if out.exists() and any(out.iterdir()): raise FileExistsError('Use a new empty external directory')
    out.mkdir(parents=True, exist_ok=True)
    provenance = {}
    def record(name, sources, locator, method):
        provenance[name] = {'sources':[{'path':s,'sha256':sha(ROOT/s)} for s in sources], 'locator':locator,'method':method}
    def text(name, value, sources, locator='', method='Verbatim text extraction'):
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf-8');record(name,sources,locator,method)
    def js(name, value, sources, locator='', method='Parsed-record extraction; no label changes'):
        text(name,json.dumps(value,ensure_ascii=False,indent=2)+'\n',sources,locator,method)
    def tab(name, rows, sources, locator='', method='Field extraction; saved numeric values without rerounding'):
        rows=list(rows);p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
        fields=list(dict.fromkeys(k for row in rows for k in row))
        with p.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
        record(name,sources,locator,method)
    tasks=lines(TASKS);results=lines(RESULTS);consensus=lines(CONSENSUS);summary=load(SUMMARY)
    assert len(tasks)==100 and len(results)==len(consensus)==800
    # A: exact source templates, plus mechanical equality with all realised generation requests.
    templates=[];template_by_id={}
    for name in STRATEGIES:
        d=PROMPT_REGISTRY[name]['3.2.0']
        for t in [d.initial,d.verification,d.revision]:
            if t is None:continue
            templates.append(asdict(t));template_by_id[t.template_id]=t
            text('A_Prompts/'+t.template_id+'.txt',t.user_template,['src/prompting.py'],t.template_id)
    assert len(templates)==6
    matches=0
    for r in results:
        for step in r['trace']:
            saved=step['prompt'];t=template_by_id[saved['template_id']];rendered=t.render(saved['variables'])
            assert rendered.user_prompt==saved['user_prompt'] and rendered.system_prompt==saved['system_prompt'] and rendered.prompt_hash==saved['prompt_hash']
            matches+=1
    assert matches==1200
    js('A_Prompts/template_registry_v3_2.json',{'registry_version':'3.2.0','templates':templates,'verification':{'saved_stage_prompts_matched':matches,'all_system_templates_null':all(t['system_template'] is None for t in templates)}},['src/prompting.py',RESULTS],'All six templates, checked against all 1,200 saved trace prompts')
    text('A_Prompts/shared_output_contract.txt',SYNTHESIS_STRESS_OUTPUT_CONTRACT,['src/prompting.py'],'SYNTHESIS_STRESS_OUTPUT_CONTRACT')
    # B: metadata reflects the implemented transformation, not independent semantics.
    mapping=[]
    for r in tasks:
        m=r['metadata'];mapping.append({'task_id':r['task_id'],'source_item_id':m['source_item_id'],'original_scifact_label':m['base_reference_label'],'reference_label':r['reference_answer'],'difficulty_category':m['difficulty_category'],'document_mode':m['document_mode'],'ordered_document_ids':json.dumps(m['context_doc_ids']),'annotated_evidence_ids':json.dumps(m['evidence_doc_ids']),'omitted_gold_ids':json.dumps(m['omitted_gold_document_ids']),'supplementary_ids':json.dumps(m['supplementary_doc_ids']),'documents_per_task':m['documents_per_task'],'base_task_id':m['base_task_id'],'base_tasks_sha256':m['base_tasks_file_sha256'],'design_sha256':m['difficulty_design_file_sha256'],'claims_sha256':m['claims_file_sha256'],'corpus_sha256':m['corpus_file_sha256']})
    tab('B_Tasks/task_to_source_mapping.csv',mapping,[TASKS],'100 tasks; original label = saved base_reference_label')
    example=next(r for r in tasks if r['task_id']=='scifact_difficulty_212_direct_control')
    js('B_Tasks/complete_example_task_212.json',example,[TASKS],example['task_id'])
    text('B_Tasks/complete_example_packet_212.txt',example['prompt']+'\n\nSUPPLIED SOURCE MATERIAL\n------------------------\n'+example['source_context']+'\n',[TASKS],example['task_id'],'Verbatim prompt and source_context with labelled separator; reference label not inserted into prompt')
    # C: actual saved exclusions and exact historical extraction example.
    six=[]
    for r in consensus:
        for c in r['claims']:
            if c['primary_support_status']==c['secondary_support_status']=='NOT_FACTUAL':
                six.append({'run_id':r['subject']['run_id'],'task_id':r['subject']['task_id'],'model':r['subject']['model']['name'],'strategy':r['subject']['strategy']['name'],**{k:c[k] for k in ['claim_id','claim','primary_support_status','secondary_support_status','support_consensus']}})
    assert len(six)==6
    tab('C_Evaluation/six_excluded_items.csv',six,[CONSENSUS],'Both original support labels NOT_FACTUAL')
    rid='a41c8273-a0a6-4410-af4a-72870698aabb';cr=next(r for r in consensus if r['subject']['run_id']==rid);rr=next(r for r in results if r['run_id']==rid);claim=next(c for c in cr['claims'] if c['claim_id'].endswith(':013'))
    js('C_Evaluation/extraction_fidelity_example.json',{'record_type':'Illustrative saved-record extraction, not systematic error-frequency estimate','run_id':rid,'task_id':cr['subject']['task_id'],'source_context':cr['subject']['source_context'],'full_response':rr['response']['raw'],'extracted_claim':claim},[RESULTS,CONSENSUS],rid+'; claim 013')
    for role,f in [('primary','atomic_primary_prompts.jsonl'),('secondary','atomic_secondary_prompts.jsonl')]:
        path=STUDY+'/atomic_consensus_v3_9/'+f;req=next(r for r in lines(path) if r['subject_run_id']==rid)
        js('C_Evaluation/saved_'+role+'_judge_request.json',req,[path],rid+'; saved attempt '+str(req['attempt_number']))
    # D: export stored estimates; never bootstrap or replace endpoints here.
    effects=[]
    for model,by_strategy in summary['paired_strategy_effects_vs_baseline'].items():
        for strategy,e in by_strategy.items():
            effects.append({'model':model,'strategy':strategy,**{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in e.items()}})
    tab('D_Results/primary_and_sensitivity_effects.csv',effects,[SUMMARY],'paired_strategy_effects_vs_baseline')
    strata=[]
    for difficulty,models in summary['paired_strategy_effects_vs_baseline_by_difficulty'].items():
        for model,strategies in models.items():
            for strategy,e in strategies.items():strata.append({'difficulty':difficulty,'model':model,'strategy':strategy,**{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in e.items()}})
    assert len(strata)==24
    tab('D_Results/exploratory_evidence_condition_effects.csv',strata,[SUMMARY],'paired_strategy_effects_vs_baseline_by_difficulty')
    means=[]
    for condition,c in summary['conditions'].items():
        for difficulty,d in c['by_difficulty'].items():means.append({'condition':condition,'difficulty':difficulty,'responses':d['responses'],'mean_response_consensus_unsupported_claim_rate':d['mean_response_consensus_unsupported_claim_rate'],'mean_response_possible_unsupported_claim_rate':d['mean_response_possible_unsupported_claim_rate']})
    tab('D_Results/evidence_condition_means.csv',means,[SUMMARY],'conditions.*.by_difficulty; source values for manuscript Figure D2')
    outcomes=[]
    for condition,c in summary['conditions'].items():
        rr=[r for r in results if f"{r['model']['provider']}:{r['model']['name']} | {r['strategy']['name']}@{r['strategy']['version']}"==condition]
        recognized=[r for r in rr if r['response']['parsed_label'] is not None]
        outcomes.append({'condition':condition,'responses':len(rr),'recognized_verdicts':len(recognized),'correct_verdicts':sum(r['response']['parsed_label']==r['ground_truth']['label'] for r in recognized),'no_evidence_predictions':sum(r['response']['parsed_label']=='NO_EVIDENCE' for r in rr),'support_binary_agreement':c['support_binary_agreement'],'consensus_unsupported_claims':c['consensus_unsupported_claims'],'uncertain_type_claims':c['consensus_hallucination_type_counts'].get('UNCERTAIN_TYPE',0)})
    tab('D_Results/verdict_and_agreement_outcomes.csv',outcomes,[RESULTS,SUMMARY],'Exact saved response counts; agreement from saved summary','Read-only consistency aggregation, not a new endpoint')
    stage=[]
    for model in sorted({r['model']['name'] for r in results}):
        for label in ['initial_generation','verification_generation','revision_generation']:
            steps=[t for r in results if r['model']['name']==model and r['strategy']['name']=='chain_of_verification' for t in r['trace'] if t['label']==label]
            stage.append({'model':model,'stage':label,'requests':len(steps),'mean_input_tokens':statistics.mean(t['response']['input_tokens'] for t in steps),'mean_output_tokens':statistics.mean(t['response']['output_tokens'] for t in steps),'mean_total_tokens':statistics.mean(t['response']['input_tokens']+t['response']['output_tokens'] for t in steps)})
    tab('D_Results/cov_stage_tokens.csv',stage,[RESULTS],'Saved CoV trace response token counts; 100 requests per model-stage','Read-only resource accounting, no monetary-cost estimate')
    for name in ['response_metrics.csv','condition_summary.csv','paired_contrasts.csv','measurement_diagnostics.json','analysis_summary.json','analysis_report.md']:
        source=STUDY+'/source_misrepresentation_analysis_v1/'+name
        # Canonical files stay in place; tiny link index replaces redundant copies.
        record('D_Results/canonical_source_misrepresentation_index.json',[source],name,'Canonical link/index; no duplicate result data')
    js('D_Results/canonical_source_misrepresentation_index.json',{'record_type':'Canonical file pointers; subsequent secondary analysis','files':[{'path':STUDY+'/source_misrepresentation_analysis_v1/'+n,'sha256':sha(ROOT/STUDY/'source_misrepresentation_analysis_v1'/n)} for n in ['response_metrics.csv','condition_summary.csv','paired_contrasts.csv','measurement_diagnostics.json','analysis_summary.json','analysis_report.md']]},[STUDY+'/source_misrepresentation_analysis_v1/analysis_summary.json'])
    # E: audit of saved settings and trace completeness.
    incomplete=[]
    for r in results:
        for t in r['trace']:
            if t['response']['finish_reason']!='completed':incomplete.append({'run_id':r['run_id'],'task_id':r['dataset']['task_id'],'model':r['model']['name'],'strategy':r['strategy']['name'],'stage':t['label'],'finish_reason':t['response']['finish_reason'],'output_tokens':t['response']['output_tokens'],'output_cap':t['request']['max_output_tokens'],'final_record_status':r['status']})
    js('E_Reproducibility/saved_request_audit.json',{'generation_requests':sum(len(r['trace']) for r in results),'final_responses':len(results),'all_generation_system_prompts_null':all(t['request']['system_prompt'] is None for r in results for t in r['trace']),'all_generation_output_caps':sorted({t['request']['max_output_tokens'] for r in results for t in r['trace']}),'generation_settings':load('config_scifact_confirmatory.json'),'incomplete_steps':incomplete,'judge_attempts':{'primary':sum(r['attempt_count'] for r in lines(STUDY+'/atomic_consensus_v3_9/atomic_primary_judgments.jsonl')),'secondary':sum(r['attempt_count'] for r in lines(STUDY+'/atomic_consensus_v3_9/atomic_secondary_judgments.jsonl'))}},[RESULTS,STUDY+'/atomic_consensus_v3_9/atomic_primary_judgments.jsonl',STUDY+'/atomic_consensus_v3_9/atomic_secondary_judgments.jsonl','config_scifact_confirmatory.json'])
    checks=[]
    def check(n,description,passed,source,scope='New read-only verification of saved records; not a claimed historical numbered check'):
        checks.append({'check_id':'EA-'+str(n).zfill(2),'description':description,'status':'PASS' if passed else 'FAIL','evidence':source,'scope':scope})
    check(1,'100 unique frozen tasks',len(tasks)==len({r['task_id'] for r in tasks})==100,TASKS)
    check(2,'Four evidence strata, 25 each',set(collections.Counter(r['metadata']['difficulty_category'] for r in tasks).values())=={25},TASKS)
    check(3,'75 original source items',len({r['metadata']['source_item_id'] for r in tasks})==75,TASKS)
    check(4,'800 unique completed responses',len({r['run_id'] for r in results})==800 and all(r['status']=='completed' for r in results),RESULTS)
    check(5,'1200 generation trace steps',matches==1200,RESULTS)
    check(6,'800 aligned consensus records',len(consensus)==800 and {r['subject']['run_id'] for r in consensus}=={r['run_id'] for r in results},CONSENSUS)
    check(7,'8326 extracted, 8320 evaluable items',sum(len(r['claims']) for r in consensus)==8326 and sum(c['support_consensus']!='EXCLUDED_NOT_FACTUAL' for r in consensus for c in r['claims'])==8320,CONSENSUS)
    check(8,'Six dual-NOT_FACTUAL excluded claims',len(six)==6,CONSENSUS)
    check(9,'Six source templates match all saved stage prompts',matches==1200,'src/prompting.py; '+RESULTS)
    check(10,'Seven incomplete intermediate audit steps; all final rows complete',len(incomplete)==7 and all(r['stage']=='verification_generation' and r['final_record_status']=='completed' for r in incomplete),RESULTS)
    tab('E_Reproducibility/integrity_checks.csv',checks,[TASKS,RESULTS,CONSENSUS],'EA-numbered checks performed now; manuscript original 1–19 checklist not located')
    js('export_provenance.json',provenance,[],'All deterministic canonical exports','Each record names source bytes and extraction method; no self-hash')
    print(json.dumps({'export_directory':str(out),'files':len(provenance),'saved_prompt_matches':matches,'checks':checks},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args();export(a.output_dir)
