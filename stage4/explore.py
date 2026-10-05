import csv
P={(x["tag"],x["page"]):x for x in csv.DictReader(open("stage4/pages.tsv"),delimiter="\t")}
I={(x["tag"],x["page"]):x for x in csv.DictReader(open("stage4/ink.tsv"),delimiter="\t")}
assert P.keys()==I.keys(), "key mismatch"
for k in P: P[k].update(I[k])
r=list(P.values())
def q(v,qs=(0,.01,.05,.1,.25,.5)): v=sorted(v); return [v[int(len(v)*x)] for x in qs]
print("contrast all:",q([int(x["contrast"]) for x in r]))
bad=[x for x in r if x["end_repeat"]=="1" and int(x["tok"])<16000]
print("contrast halluc:",sorted(int(x["contrast"]) for x in bad))
cap=[x for x in r if int(x["tok"])>=16000]
print("contrast capped:",sorted(int(x["contrast"]) for x in cap))
blank=[x for x in r if x["chars"]=="0"]
print("contrast blank(chars0):",q([int(x["contrast"]) for x in blank],(0,.5,.9,.95,.99)), "max", max(int(x["contrast"]) for x in blank))
print("ink blank:",q([float(x["ink"]) for x in blank],(0,.5,.9,.95,.99)))
for c in (20,30,40,50,60):
    s=[x for x in r if int(x["contrast"])<c]
    print("contrast<%d: %d pages, median chars %s" % (c,len(s),q([int(x["chars"]) for x in s],(.5,))))
