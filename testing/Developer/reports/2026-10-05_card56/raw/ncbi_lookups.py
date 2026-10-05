import json
import time
import urllib.parse
import urllib.request

B="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
def g(path,**p):
    p.update(retmode="json",tool="diag",email="noreply@users.noreply.github.com")
    time.sleep(0.4)
    return json.load(urllib.request.urlopen(B+path+"?"+urllib.parse.urlencode(p),timeout=30))
out=[]
def es(db,term,**k):
    r=g("esearch.fcgi",db=db,term=term,retmax=k.get("retmax",3)); s=r["esearchresult"]
    rec={"call":f"esearch db={db} term={term}","count":s.get("count"),"ids":s.get("idlist"),"translation":s.get("querytranslation")}
    out.append(rec); print(rec); return s
def sm(db,ids):
    r=g("esummary.fcgi",db=db,id=",".join(ids)); res=r["result"]
    for i in ids:
        d=res.get(i,{}); rec={"call":f"esummary db={db} id={i}","title":d.get("scientificname") or d.get("title") or d.get("assemblyname") or d.get("name"),"extra":{k:d.get(k) for k in("rank","division","commonname","organism","speciesname","assemblyaccession")}}
        out.append(rec); print(rec)
for term in ["SARS-CoV-2[All Names]","Severe acute respiratory syndrome coronavirus 2[All Names]","Mycobacterium tuberculosis[All Names]","Salmonella enterica[All Names]","SARS coronavirus 2[All Names]"]:
    s=es("taxonomy",term)
    if s["idlist"]: sm("taxonomy",s["idlist"][:1])
s=es("medgen","SARS[All Fields]",retmax=5); sm("medgen",s["idlist"][:3])
s=es("medgen","SARS-CoV-2[All Fields]",retmax=3)
s=es("taxonomy","Illumina[All Names]")
s=es("assembly","txid1773[Organism:exp]",retmax=1)
s=es("sra","txid2697049[Organism:exp] AND Illumina[Platform]",retmax=1)
with open("ncbi_lookups.json", "w") as f:
    json.dump(out, f, indent=1)
print(len(out))
