import json, sys, glob
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding='utf-8')
R, OUT, JOUT = sys.argv[1], sys.argv[2], sys.argv[3]
A = [x for f in sorted(glob.glob(R + '/*.json')) for x in json.load(open(f, encoding='utf-8'))]
json.dump(A, open(JOUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
D = {x['id']: x for x in A}
U = 'https://github.com/sarsonj/rodokmen-skill/issues/'


def src(x):
    s = sorted(set(x.get('sources') or []))
    return ', '.join(f'[#{n}]({U}{n})' for n in s)


def cell(t):
    return (t or '').replace('|', '\\|').replace('\n', ' ')


def table(ids):
    h = "| ID | Item | Area | Status | Effort | Action | Upstream |\n|---|---|---|---|---|---|---|"
    rows = [f"| {D[i]['id']} | {cell(D[i]['title'])} | {cell(D[i]['area'])} | {D[i]['status']} | {D[i]['effort']} | {D[i]['recommendation']} | {src(D[i])} |" for i in ids]
    return h + '\n' + '\n'.join(rows)


SPRINTS = [
    ("Sprint 1: correctness, privacy and safety fixes (small, high value)",
     "Things that are wrong today or can leak data. Mostly one-liners or small checks.",
     ['I18-1', 'PR22', 'PR200', 'I114-1', 'I174-3', 'PR140', 'I25-1', 'I68-1', 'I162-1', 'I204-1', 'I143-1']),
    ("Sprint 2: token budget and helper (sub-agent) discipline",
     "Upstream users repeatedly burned their 5-hour limit on helpers re-reading scans. Cheap guardrails plus a faster export.",
     ['I90-1', 'I90-2', 'I30-7', 'I34-1', 'I43-2', 'I119-1', 'PR120', 'PR202', 'I204-2', 'PR216', 'PR203']),
    ("Sprint 3: method guide corrections (reference/*.md, SKILL.md)",
     "Documentation errors that led agents to false \"not online\" conclusions, plus proven research tips.",
     ['I188-1', 'I192-1', 'I192-2', 'I167-16', 'I167-14', 'I97-1', 'I83-1', 'I133-1', 'I137-1', 'I130-1', 'I177-1', 'I208-7', 'I213-8', 'I214-1', 'I127-5', 'I67-9']),
    ("Sprint 4: bigger features and PR merges",
     "Larger chunks; review each PR diff before merging. Overlaps: PR201 supersedes PR76/PR126/PR135 (fix the Kufa/Kufová surname bug when merging); PR128 preferred over PR13/PR20; PR77 goes on top of PR201; PR89 overlaps PR22.",
     ['PR201', 'PR187', 'PR139', 'PR89', 'PR189', 'I54-2', 'I161-7', 'I30-2', 'I30-17', 'PR128', 'I194-1', 'I30-18']),
]
TOS5 = [x['id'] for x in A if x['risk'] == 'tos' and x['status'] != 'done' and x['recommendation'] != 'skip']
SPRINTS.append(("Sprint 5: archive access workarounds (accepted 20. 11. 2026)",
    "Decision: accept the proposed workarounds to get access where possible. Keep the brzda (rate limiting) and the "
    "hlídač in place for every new path, so the archives see human-like load, and never publish scans other than crops on our own web.",
    TOS5))
DEFER = ['I67-6', 'I154-1', 'I154-2', 'I17-1', 'PR92', 'I171-1']
WONT = ['I43-1', 'PR42', 'PR52', 'PR110']
used = {i for _, _, ids in SPRINTS for i in ids}
missing = [i for i in used | set(DEFER) | set(WONT) if i not in D]
assert not missing, missing
park = set(DEFER) | set(WONT)

dec = [x for x in A if x['recommendation'] == 'needs-decision' and x['id'] not in used and x['id'] not in park]
done = [x for x in A if x['status'] == 'done' and x['id'] not in used and x not in dec]
skip = [x for x in A if x['recommendation'] == 'skip' and x['status'] != 'done' and x['id'] not in used]
done = [x for x in done if x['id'] not in park]
skip = [x for x in skip if x['id'] not in park]
taken = {id(x) for x in dec + done + skip}
rest = [x for x in A if x['id'] not in used and x['id'] not in park and id(x) not in taken]


def grp(x):
    a = (x['area'] + ' ' + x['kind']).lower()
    if x['kind'] == 'web' or 'template/web' in a or 'astro' in a or 'web template' in a:
        return 'Web template'
    if x['kind'] == 'new-source' or 'portaly' in a:
        return 'Sources & archives (portaly.md, new tools)'
    if 'tools/' in a or x['kind'] in ('tooling', 'bug'):
        return 'Tools (tools/*.py)'
    if x['kind'] in ('platform', 'infra', 'install') or 'install' in a:
        return 'Platform, install, other agents'
    if x['kind'] == 'method-docs' or '.md' in a:
        return 'Method docs (SKILL.md, reference/)'
    return 'Ideas & other'


VO = {'high': 0, 'med': 1, 'low': 2}
EO = {'S': 0, 'M': 1, 'L': 2}
G = defaultdict(list)
for x in rest:
    G[grp(x)].append(x)

L = []
w = L.append
w("# Backlog: upgrades from upstream sarsonj/rodokmen-skill\n")
w(f"_Generated 20. 11. 2026 from upstream's 109 open issues and 53 open PRs, triaged against our copy at 0.10.2 (same as upstream main `8b1ea6e`). {len(A)} atomic items in total._\n")
w("## Licence\n")
w("Upstream is **MIT** (© 2026 Jindřich Šaršon). Personal use, modification and redistribution are allowed. "
  "The only obligation is to keep `LICENSE` and the copyright notice in copies we distribute. "
  "When cherry-picking from an unmerged PR by another contributor, credit the author in the commit (`Co-Authored-By`).\n")
w("MIT covers the code only. **Archive content and portals have their own terms** (robots.txt, terms of use, daily limits); "
  "upstream removed its SOA Třeboň downloader at the archive's request. Items marked `tos` work around such limits and are parked under *Needs decision*.\n")
w("## Decisions (20. 11. 2026)\n")
w("- **Repository:** `origin` = [xkazm04/rodokmeny](https://github.com/xkazm04/rodokmeny), `upstream` = sarsonj/rodokmen-skill. Update check (`verze.py`), install command and issue links point to our fork.\n"
  "- **Order:** Sprints 1–4 one after another, then Sprint 5.\n"
  "- **Other AI tools:** Anthropic products only (Claude Code, Claude desktop, Claude in Chrome). Codex, Cursor, Devin, OMP support is out of scope.\n"
  "- **Archive workarounds:** accepted, see Sprint 5.\n"
  "- **Living persons' data:** deferred until the PR/issue sprints are done. The next roadmap step is a UI/UX redesign of the web, which will decide how living persons are shown.\n")
w("## How to read this\n")
w("- **Status** is the state in *our* code: `not_done`, `partial`, `done`, `unclear`. Each was checked against the code; file:line evidence is in the JSON.\n"
  "- **Action**: `merge-pr` (PR applies as is), `cherry-pick` (take part of a PR), `adapt` (good idea, rewrite for current code), `adopt` (implement from the issue), `needs-decision`, `skip`.\n"
  "- **Effort**: S ≤ half a day, M about 1–2 days, L more.\n"
  "- Full detail per item (evidence, rationale, risk): [`docs/backlog/upstream-triage.json`](docs/backlog/upstream-triage.json).\n")
c = Counter(x['status'] for x in A)
r = Counter(x['recommendation'] for x in A)
w(f"**Totals:** {c['not_done']} not done · {c['partial']} partial · {c['done']} already done · {r['needs-decision']} need a decision · {r['skip']} skip.\n")
for t, d, ids in SPRINTS:
    w(f"## {t}\n\n{d}\n\n" + table(ids) + "\n")
w("<details><summary>Why each sprint item matters (rationale and evidence)</summary>\n")
for t, d, ids in SPRINTS:
    for i in ids:
        w(f"- **{i}**: {cell(D[i]['why'])} _Evidence:_ {cell(D[i]['evidence'])}")
w("\n</details>\n")
w("## Deferred to the UI/UX redesign (living persons' data)\n")
w(table(DEFER) + "\n")
w("## Won't do (other AI tools)\n")
w(table(WONT) + "\n")
w("## Needs decision (terms of use, privacy, product direction)\n")
w("Not to be done without an explicit call. `tos` = would work around an archive's access rules; `privacy` = touches publication of living persons' data.\n")
w("| ID | Item | Risk | Value | Upstream | Why |\n|---|---|---|---|---|---|")
for x in sorted(dec, key=lambda x: (x['risk'] != 'tos', x['risk'] != 'privacy', VO[x['value']], x['id'])):
    w(f"| {x['id']} | {cell(x['title'])} | {x['risk']} | {x['value']} | {src(x)} | {cell(x['why'])} |")
w("")
w("## Remaining backlog by area\n")
w("Sorted by value, then effort. Pull from here once the sprints are done.\n")
for g in ['Tools (tools/*.py)', 'Method docs (SKILL.md, reference/)', 'Sources & archives (portaly.md, new tools)',
          'Web template', 'Platform, install, other agents', 'Ideas & other']:
    xs = sorted(G.get(g, []), key=lambda x: (VO[x['value']], EO[x['effort']], x['id']))
    if not xs:
        continue
    w(f"### {g} ({len(xs)})\n")
    w("| ID | Item | Value | Effort | Status | Action | Risk | Upstream |\n|---|---|---|---|---|---|---|---|")
    for x in xs:
        w(f"| {x['id']} | {cell(x['title'])} | {x['value']} | {x['effort']} | {x['status']} | {x['recommendation']} | {x['risk']} | {src(x)} |")
    w("")
w(f"## Already done in 0.10.2 ({len(done)}), nothing to do\n\n<details><summary>Show</summary>\n")
for x in sorted(done, key=lambda x: x['id']):
    w(f"- {x['id']} {cell(x['title'])}: {cell(x['evidence'])}")
w("\n</details>\n")
w(f"## Skipped ({len(skip)})\n\n<details><summary>Show</summary>\n")
for x in sorted(skip, key=lambda x: x['id']):
    w(f"- {x['id']} {cell(x['title'])}: {cell(x['why'])}")
w("\n</details>\n")
open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('ok total', len(A), 'sprint', len(used), 'decision', len(dec), 'rest', len(rest), 'done', len(done), 'skip', len(skip))
print({g: len(v) for g, v in G.items()})
