import glob
import json
import os
import re

here=os.path.dirname(os.path.abspath(__file__))
for f in sorted(glob.glob(here+"/raw/run*.json"),key=lambda x:int(re.findall(r"run(\d+)",x)[0])):
    with open(f) as fp: d=json.load(fp); ev=d["events"]
    think=next(e["payload"] for e in ev if e["type"]=="think")
    tools=[e["payload"]["tool"] for e in ev if e["type"]=="tool_start"]
    cites=sorted({e["payload"]["source_id"] for e in ev if e["type"]=="citation"})
    txt="".join(e["payload"]["text"] for e in ev if e["type"]=="token")
    body=txt.split("Where this answer comes from")[0]
    fmf=bool(re.search(r"familial mediterranean",body,re.IGNORECASE)); fmf_any=bool(re.search(r"familial mediterranean",txt,re.IGNORECASE))
    done=next(e["payload"] for e in ev if e["type"]=="done")
    plan=next(e["payload"]["narrative"] for e in ev if e["type"]=="plan")
    print(d["run"],d["seconds"],"FMF_body",fmf,"FMF_any",fmf_any,"ents",think["resolved_entities"],"|",plan[:90],"|",tools,"|",cites,"|",done["trust_outcome"])
