#!/usr/bin/env python3
"""Stage 1 of person grounding: parse a PERSON mention into fields instead of string-matching it.

parse(text, norm) -> dict with
  kind      person | title (office only: "Director of Agriculture") | list ("Paine and Williams")
            | initials (signature/pen-name: "W. A. D. S.") | empty
  hon       honorifics, lower-case, in order ("dr", "sir", "gate mudaliyar")
  office    office words that preceded the name ("consul" in "Mr. Consul Stevens")
  given     [(initial, full_name_or_None), ...]  e.g. "J. L. Shand" -> [("j",None),("l",None)];
            "John Hughes" -> [("j","john")]; Wm./Thos./Geo. are expanded to full names
  surname   display form ("de Silva", "St. John", "Seton-Kale")
  skey      matching key: ascii, lower, no spaces/dots/hyphens/apostrophes ("desilva")
  suffix    degrees and post-nominals ("fic", "cbe", "esq"); generation ("junr") goes to gen
  gen       "jr" | "sr" | ""
  gender    "f" | "m" | ""   (from honorifics only)
The name comes from `norm` (the extractor often resolved "Mr. Petch" to "T. Petch" from context); the
honorific comes from whichever of text/norm carries one."""
import re, unicodedata

HON = {  # surface token (no dot, lower) -> canonical honorific
    "mr": "mr", "mister": "mr", "messrs": "messrs", "mrs": "mrs", "miss": "miss", "misses": "misses",
    "dr": "dr", "doctor": "dr", "prof": "prof", "professor": "prof", "sir": "sir",
    "rev": "rev", "revd": "rev", "reverend": "rev", "hon": "hon", "honble": "hon", "honourable": "hon",
    "honorable": "hon", "capt": "capt", "captain": "capt", "major": "major", "col": "col", "colonel": "col",
    "lieut": "lieut", "lieutenant": "lieut", "lt": "lieut", "general": "gen", "gen": "gen",
    "admiral": "admiral", "commander": "commander", "sergeant": "sergeant", "surgeon": "surgeon",
    "mudaliyar": "mudaliyar", "mudaliar": "mudaliyar", "modliar": "mudaliyar", "mudliyar": "mudaliyar",
    "mohandiram": "mohandiram", "muhandiram": "mohandiram", "arachchi": "arachchi",
    "ratemahatmaya": "ratemahatmaya", "adigar": "adigar", "dissawa": "dissawa",
    "herr": "herr", "mons": "mons", "monsieur": "mons", "mme": "mme", "madame": "mme", "mdme": "mme",
    "mlle": "mlle", "mademoiselle": "mlle", "senor": "senor", "signor": "signor", "senhor": "senor",
    "father": "father", "fr": "father", "abbe": "abbe", "brother": "brother", "sister": "sister", "bishop": "bishop",
    "archdeacon": "archdeacon", "canon": "canon", "dean": "dean", "judge": "judge", "justice": "justice",
    "baron": "baron", "baroness": "baroness", "count": "count", "countess": "countess",
    "lord": "lord", "lady": "lady", "duke": "duke", "duchess": "duchess", "earl": "earl",
    "marquis": "marquis", "marquess": "marquis", "viscount": "viscount", "prince": "prince",
    "princess": "princess", "king": "king", "queen": "queen", "emperor": "emperor", "empress": "empress",
    "sultan": "sultan", "maharaja": "maharaja", "maharajah": "maharaja", "raja": "raja", "rajah": "raja",
    "nawab": "nawab", "sheikh": "sheikh", "pope": "pope", "the": "the",
}
GATE = {"gate"}  # "Gate Mudaliyar"
FEMALE = {"mrs", "miss", "misses", "lady", "mme", "mlle", "countess", "baroness", "princess", "queen",
          "empress", "duchess", "sister"}
MALE = {"mr", "sir", "lord", "herr", "mons", "senor", "signor", "father", "brother", "baron", "count",
        "duke", "earl", "marquis", "viscount", "prince", "king", "emperor", "sultan", "maharaja", "raja",
        "nawab", "sheikh", "pope", "bishop", "archdeacon", "canon", "mudaliyar", "mohandiram"}
# Titles that are part of the identity ("Lord Derby" is not "Mr. Derby"; "King Edward" has no surname).
IDENTITY = {"lord", "lady", "duke", "duchess", "earl", "marquis", "viscount", "prince", "princess", "king",
            "queen", "emperor", "empress", "sultan", "maharaja", "raja", "nawab", "pope", "baroness",
            "countess"}
# Office words: a mention made only of these (plus "of", places, ...) is a title, not a name.
OFFICE = {
    "director", "governor", "secretary", "chairman", "president", "vice-president", "agent", "superintendent",
    "editor", "correspondent", "commissioner", "collector", "minister", "consul", "vice-consul", "envoy",
    "chancellor", "inspector", "manager", "planter", "assistant", "analyst", "botanist", "entomologist",
    "mycologist", "chemist", "officer", "member", "treasurer", "registrar", "curator", "surveyor",
    "conservator", "chief", "asst", "govt", "supt", "secy", "dir", "commr", "insp", "offr", "prest", "government", "colonial", "deputy", "acting", "chairman", "magistrate",
    "proprietor", "visiting", "agricultural", "assistant-director", "controller", "warden", "auditor",
    "attorney-general", "solicitor-general", "attorney", "solicitor", "clerk", "headman", "lecturer",
    "instructor", "principal", "headmaster", "ambassador", "viceroy", "premier", "mayor", "senator",
    "delegate", "representative", "speaker", "excellency", "highness", "majesty", "lordship", "worship",
    "author", "writer", "reader", "subscriber", "correspondent", "native", "planters", "official",
    "his", "her", "our", "their", "a", "an", "chairman", "hony", "honorary", "joint", "general-manager",
    "postmaster", "postmaster-general", "surveyor-general", "auditor-general", "governor-general",
    "colonial-secretary", "economic", "government-agent", "assistant-government-agent", "g.a.", "a.g.a.",
}
FUNC = {"of", "the", "to", "for", "in", "at", "on", "and", "&", "with", "from", "by"}
PARTICLES = {"de", "da", "das", "do", "dos", "van", "von", "der", "den", "la", "le", "du", "di", "del",
             "della", "st", "ste", "saint", "ten", "ter", "op", "al", "el", "bin", "ibn", "y", "of"}
DROP = {"von", "van", "der", "den", "ten", "ter", "op", "vander", "vonder"}   # often omitted: "Liebig" = "von Liebig"
ABBR = {"wm": "william", "thos": "thomas", "geo": "george", "chas": "charles", "jas": "james",
        "jno": "john", "robt": "robert", "richd": "richard", "edwd": "edward", "edw": "edward",
        "alexr": "alexander", "alex": "alexander", "benj": "benjamin", "saml": "samuel", "fredk": "frederick",
        "fred": "frederick", "hy": "henry", "jos": "joseph", "danl": "daniel", "dan": "daniel",
        "wl": "william", "gul": "william", "ed": "edward", "ernst": "ernst", "arch": "archibald",
        "archd": "archibald", "nathl": "nathaniel", "steph": "stephen", "phil": "philip", "theo": "theodore",
        "matt": "matthew", "andw": "andrew", "abm": "abraham", "isc": "isaac", "chris": "christopher",
        "xtopher": "christopher", "and": None}
GEN = {"junr": "jr", "jun": "jr", "jr": "jr", "junior": "jr", "senr": "sr", "sen": "sr", "sr": "sr",
       "senior": "sr", "ii": "jr", "iii": "jr"}
DEGREES = {
    "esq", "esqr", "jp", "ma", "ba", "bsc", "msc", "dsc", "phd", "md", "mb", "frs", "fls", "fcs", "fic",
    "fgs", "fzs", "fes", "cmg", "kcmg", "gcmg", "cb", "kcb", "cbe", "obe", "mbe", "kbe", "gbe", "cie", "kcie",
    "csi", "kcsi", "iso", "mlc", "mrcvs", "frcs", "mrcs", "lrcp", "frcp", "lld", "dd", "rm", "arcs", "mrac",
    "frgs", "fras", "fsa", "kc", "qc", "mp", "dl", "nda", "fhas", "rn", "re", "ra", "cs", "ccs", "vd", "ics",
    "mice", "amice", "fcgi", "frse", "frhs", "frmets", "fias", "fsi", "mrsi", "dipagr", "bsa", "msa", "bagr",
    "magr", "dic", "arcsc", "fibd", "lic", "lms", "ims", "cvo", "mvo", "kcvo", "dso", "mc", "td", "rnr",
    "frsa", "fsc", "gcb", "kg", "kt", "bart", "bt", "mrsl", "fsl", "fzsl", "frcsi", "dcl", "ll", "ms",
    "frms", "fcis", "aic", "ics", "jp", "upm", "mla", "mra", "mrasl", "fla", "fma", "frai", "frsl",
}
WORD = re.compile(r"[^\s,]+")

def ascii_lower(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

def bare(tok):
    return re.sub(r"[.’'`]", "", ascii_lower(tok))

def skey(s):
    return re.sub(r"[^a-z]", "", ascii_lower(s))

def is_initial(tok):  # "J." "J" (single letter) but not "A" article in titles (handled by caller)
    return bool(re.fullmatch(r"[A-Za-z]\.?", tok))

def clean(s):
    return s.replace("’", "'").strip().strip("*_ ")

def split_tokens(s):
    s = re.sub(r"\b([A-Za-z])\.(?=[A-Za-z]\.)", r"\1. ", s)        # J.L. -> J. L.
    s = re.sub(r"\b([A-Z])\.([A-Z]{2,}|[A-Z][a-z]{2,})", r"\1. \2", s)  # J.Shand, C.DRIEBERG
    return s

def looks_degree(tok, orig):
    b = bare(tok)
    if b in DEGREES:
        return True
    # dotted capitals after the surname: "F.I.C.", "M.R.C.V.S.", "B.Sc."
    return bool(re.fullmatch(r"(?:[A-Z][A-Za-z]?\.){2,}[A-Za-z]?\.?", orig))

def parse(text, norm=""):
    src = clean(norm or text)
    out = {"kind": "person", "hon": [], "office": [], "given": [], "surname": "", "skey": "",
           "suffix": [], "gen": "", "gender": ""}
    low = " " + ascii_lower(src) + " "
    # lists: "Paine and Williams", "Mr. and Mrs. Cotton" (norm usually already singular), "A, B, C"
    if re.search(r"\s(and|&)\s", low) and not re.search(r"^\s*(mr|mrs|dr)\.? (and|&) (mrs|mr)\.? ", low.strip() + " "):
        lw = [bare(t) for t in WORD.findall(low)]
        out["kind"] = "title" if any(w in OFFICE or w in {"of", "for", "the"} for w in lw) else "list"
        return out
    # inverted "Peiris, H. C." / suffix "John Hughes, F.I.C."
    parts = [p.strip() for p in src.split(",")]
    head, tail = parts[0], parts[1:]
    suffix_tokens = []
    rest = []
    for p in tail:
        toks = WORD.findall(p)
        if toks and (all(looks_degree(t, t) or bare(t) in GEN for t in toks) or skey(p) in DEGREES):
            suffix_tokens += toks
        else:
            rest.append(p)
    if rest:
        r0 = WORD.findall(rest[0])
        if len(rest) == 1 and r0 and all(is_initial(t) or bare(t) in ABBR or bare(t) in HON or
                                         (t[:1].isupper() and len(WORD.findall(head)) <= 2) for t in r0) \
                and len(WORD.findall(head)) <= 3:
            head = rest[0] + " " + head      # inverted: "Peiris, H. C." -> "H. C. Peiris"
        elif not any(bare(t) in OFFICE for t in WORD.findall(head)):
            out["kind"] = "list"; return out
    hl = [bare(t) for t in WORD.findall(head)]
    if rest and any(b in OFFICE for b in hl) or (hl and hl[0] != "of" and any(b in FUNC for b in hl)
                                                  and not re.match(r"(duke|earl|prince|princess|marquis|lord|lady|king|queen|bishop|archbishop|sultan|maharaja|raja|nawab|count|baron|duchess)\b", hl[0])):
        out["kind"] = "title"; return out
    toks = WORD.findall(split_tokens(head))
    # honorifics from the surface text as well (norm often drops them)
    def take_hon(ts, sink):
        i = 0
        while i < len(ts):
            b = bare(ts[i])
            if b in GATE and i + 1 < len(ts) and bare(ts[i + 1]) in HON and HON[bare(ts[i + 1])] == "mudaliyar":
                sink.append("gate mudaliyar"); i += 2; continue
            hyph = b.split("-")
            if b in HON and not (b in {"king", "queen", "count", "dean", "judge", "canon", "major", "general"}
                                 and i + 1 >= len(ts)):
                h = HON[b]
                if h != "the":
                    sink.append(h)
                i += 1; continue
            if len(hyph) > 1 and all(x in HON or x in OFFICE for x in hyph):   # Major-General, Lieut.-Col.
                sink += [HON.get(x, x) for x in hyph]; i += 1; continue
            break
        return ts[i:]
    hons = []
    toks = take_hon(toks, hons)
    surf_hons = []
    take_hon(WORD.findall(split_tokens(text)), surf_hons)
    for h in surf_hons:
        if h not in hons:
            hons.append(h)
    # office words between honorific and name: "Mr. Consul Stevens", "Director Thwaites"
    office = []
    while toks and (bare(toks[0]) in OFFICE or bare(toks[0]) in FUNC) and len(toks) > 1 \
            and not (is_initial(toks[0]) and toks[0][0].isupper()):
        office.append(bare(toks[0])); toks = toks[1:]
    # trailing degrees / generation without a comma
    while toks and len(toks) > 1 and (looks_degree(toks[-1], toks[-1]) or bare(toks[-1]) in GEN):
        suffix_tokens.insert(0, toks[-1]); toks = toks[:-1]
    for t in suffix_tokens:
        b = bare(t)
        if b in GEN: out["gen"] = GEN[b]
        else: out["suffix"].append(b)
    out["hon"] = hons; out["office"] = office
    out["gender"] = "f" if any(h in FEMALE for h in hons) else "m" if any(h in MALE for h in hons) else ""
    if not toks:
        out["kind"] = "title" if (office or hons) else "empty"; return out
    lowtoks = [bare(t) for t in toks]
    # title-only: function words or office words inside what is left ("Director of Agriculture")
    if any(b in FUNC for b in lowtoks) or all(b in OFFICE for b in lowtoks) or \
            (office and any(b in OFFICE for b in lowtoks)) or bare(toks[-1]) in OFFICE:
        out["kind"] = "title"; return out
    if all(is_initial(t) for t in toks):
        out["kind"] = "initials"
        out["given"] = [(bare(t), None) for t in toks]; return out
    # surname = last token, extended leftwards over particles ("de Silva", "van der Stok", "St. John")
    j = len(toks) - 1
    while j - 1 >= 0 and bare(toks[j - 1]) in PARTICLES and not is_initial(toks[j - 1]):
        j -= 1
    if j == 0 and len(toks) > 1 and bare(toks[0]) in PARTICLES:   # "De Silva" alone
        j = 0
    sur = toks[j:]
    given = []
    for t in toks[:j]:
        b = bare(t)
        if is_initial(t):
            given.append((b, None))
        elif b in ABBR and ABBR[b]:
            given.append((ABBR[b][0], ABBR[b]))
        elif re.fullmatch(r"[a-z][a-z'\-]+", b):
            given.append((b[0], b))
    surname = " ".join(sur)
    if surname.isupper() or surname.islower():
        surname = " ".join(w if bare(w) in PARTICLES else w.capitalize() for w in sur)
        surname = re.sub(r"-(\w)", lambda m: "-" + m.group(1).upper(), surname)
    core = list(sur)
    while len(core) > 1 and bare(core[0]) in DROP:
        core = core[1:]
    out["given"] = given; out["surname"] = surname; out["skey"] = skey(" ".join(core))
    if not out["skey"]:
        out["kind"] = "empty"
    # identity titles with no given names: "King Edward", "Lord Derby", "Duke of Argyll" -> title in the key
    idt = [h for h in hons if h in IDENTITY]
    if idt and not given and out["kind"] == "person":
        out["skey"] = idt[0] + ":" + out["skey"]
    return out

# ---------------- name compatibility (shared by build_profiles.py and wd/ground_wikidata.py) ----------
def pos_ok(a, b):
    return a[0] == b[0] and (a[1] is None or b[1] is None or a[1] == b[1])

def given_compat(g1, g2):
    """J. Shand ~ J. L. Shand (prefix); Kelway Bamber ~ M. Kelway Bamber (subsequence, only when the shorter
    form carries a full given name that matches); John ~ J.; John !~ James; W. !~ J."""
    s, l = (g1, g2) if len(g1) <= len(g2) else (g2, g1)
    if all(pos_ok(a, b) for a, b in zip(s, l)):
        return True
    if not any(n for _, n in s):
        return False
    i = 0; fullhit = False
    for a in s:
        while i < len(l) and not pos_ok(a, l[i]):
            i += 1
        if i == len(l):
            return False
        fullhit |= bool(a[1] and l[i][1] == a[1]); i += 1
    return fullhit

# ---------------- source support for model-supplied given names ------------------------------------
_GAP = r"[\s,]*"
_MID = r"(?:(?!and\b|of\b|the\b|or\b|&)[A-Za-z][\w'-]*\.?\s+)?"   # at most one middle word, not a function word

def supported_given(p, text):
    """How much of p's given names does the article print next to the surname?
    Returns (given, status): status "full" = every full given name printed as a whole word; "initials" = only
    initials printed for some full names (those are downgraded to initials -- "Mr. J. Watt" does NOT support
    "James Watt"); "none" = no matching name printed. Surname and names need word boundaries ("Smithson" is not
    "Smith"); an initial cannot be the first letter of a longer word."""
    if not p.get("given") or not p.get("surname"):
        return [], "none"
    sur = r"\b" + re.escape(p["surname"].split()[-1]) + r"\b"
    parts = []
    for k, (i, n) in enumerate(p["given"]):
        ini = r"\b" + re.escape(i) + r"(?![A-Za-z])\.?"
        if n:   # the full name, or a printed abbreviation of it ("Wm." for William, "Thos." for Thomas)
            forms = [n] + sorted(k for k, v in ABBR.items() if v == n and k != n)
            full = "|".join(r"\b" + re.escape(f) + r"\b\.?" for f in forms)
            parts.append(f"(?P<g{k}>{full}|{ini})")
        else:
            parts.append(f"(?P<g{k}>{ini})")
    gp = _GAP.join(parts)
    best = None
    for pat in (gp + _GAP + _MID + sur, sur + r",?\s*" + gp + r"(?![A-Za-z])"):
        for m in re.finditer(pat, text, re.I):
            kept = [(i, n if n and len(m.group(f"g{k}").rstrip(".")) > 1 else None) for k, (i, n) in enumerate(p["given"])]
            score = sum(1 for _, n in kept if n)
            if best is None or score > best[0]:
                best = (score, kept)
    if best is None:
        return [], "none"
    full = sum(1 for _, n in p["given"] if n)
    return best[1], ("full" if best[0] == full else "initials")

def display(p):
    if p["kind"] != "person":
        return ""
    g = " ".join((n.capitalize() if n else i.upper() + ".") for i, n in p["given"])
    idt = [h for h in p["hon"] if h in IDENTITY] if not p["given"] else []
    s = " ".join(x for x in [" ".join(h.capitalize() for h in idt), g, p["surname"]] if x)
    return s + (" Jr." if p["gen"] == "jr" else " Sr." if p["gen"] == "sr" else "")

if __name__ == "__main__":
    # The examples that used to live here are now assertions in tests/test_persons.py:
    #     python3 -m pytest ner/persons/tests -q
    import sys
    for line in sys.argv[1:]:
        q = parse(line)
        print(f"{line!r} -> {q['kind']} {display(q)!r} hon={q['hon']} skey={q['skey']}")
