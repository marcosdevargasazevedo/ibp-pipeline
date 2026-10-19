"""Regenerate src/dependency-evidence.json by scanning an unpacked IBP repository.
Usage: python tools/extract_rule_dependencies.py /path/to/repo
Static declarations only — NOT the resolved Snakemake DAG.
"""
from pathlib import Path
import sys,re,ast,json,hashlib
if len(sys.argv)!=2:raise SystemExit('Usage: python tools/extract_rule_dependencies.py PATH_TO_REPOSITORY')
root=Path(sys.argv[1]).expanduser().resolve()
if not (root/'Snakefile').is_file():raise SystemExit('Snakefile not found')
# parse sections from rule blocks while shielding indentation multiline code bodies
rule_re=re.compile(r'^(rule|checkpoint)\s+([A-Za-z_]\w*)\s*:',re.M)
sect_re=re.compile(r'^    (input|output|log)\s*:\s*(.*)$',re.M)
def split_top(s):
 res=[];cur='';lvl=0;quote=None;esc=False
 for c in s:
  if quote:
   cur+=c
   if esc:esc=False
   elif c=='\\':esc=True
   elif c==quote:quote=None
  elif c in "\"'":quote=c;cur+=c
  elif c in '([{':lvl+=1;cur+=c
  elif c in ')]}':lvl-=1;cur+=c
  elif c==',' and lvl==0:
   if cur.strip():res.append(cur.strip())
   cur=''
  else:cur+=c
 if cur.strip():res.append(cur.strip())
 return res

def parse_block(block):
 # use tokenize-via-ast for comma-delimited expressions, comments ignored
 s='\n'.join(line.split('#')[0] for line in block.splitlines() if line.strip() and not line.lstrip().startswith('#'))
 try:
  tree=ast.parse('['+s+']',mode='eval')
  vals=[]
  for el in tree.body.elts:
   label=None
   if isinstance(el,ast.NamedExpr): el=el.value
   if isinstance(el,ast.Call) and isinstance(el.func,ast.Name) and el.func.id in ('directory','temp','protected','ancient','touch','ensure','dynamic','pipe') and el.args:el=el.args[0]
   try: expr=ast.unparse(el)
   except:expr=s.strip()
   vals.append(expr)
  return vals
 except SyntaxError:
  # sections may be named keyword assignments; ast.parse as a call's kwargs
  try:
   call=ast.parse('f('+s+')',mode='eval').body
   return [ast.unparse(a) for a in call.args]+[ast.unparse(k.value) for k in call.keywords]
  except SyntaxError:
   return [x.split('=',1)[-1].strip() for x in split_top(s) if x.strip()]

def canonical(s):
 try:
  n=ast.parse(s,mode='eval').body
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('directory','temp','protected','ancient','touch','ensure','dynamic','pipe') and n.args:n=n.args[0]
  # literal and fstring safe symbolic normalization preserving variable placeholders
  def val(n):
   if isinstance(n,ast.Constant) and isinstance(n.value,str):return n.value
   if isinstance(n,ast.Name):return '${'+n.id+'}'
   if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add):
    a,b=val(n.left),val(n.right)
    return a+b if a is not None and b is not None else None
   if isinstance(n,ast.JoinedStr):
    p=[]
    for x in n.values:
     if isinstance(x,ast.Constant):p.append(str(x.value))
     elif isinstance(x,ast.FormattedValue):
      if isinstance(x.value,ast.Name):p.append('${'+x.value.id+'}')
      else:return None
     else:return None
    return ''.join(p)
   return None
  return val(n)
 except:return None

rules=[]
for i in range(1,9):
 path=root/'workflow'/'rules'/f'module{i}.smk'; raw=path.read_text()
 matches=list(rule_re.finditer(raw))
 for j,m in enumerate(matches):
  block=raw[m.end():matches[j+1].start() if j+1<len(matches) else len(raw)]
  sections=list(sect_re.finditer(block)); fields={'input':[],'output':[],'log':[]}
  for k,sec in enumerate(sections):
   start=sec.end();end=sections[k+1].start() if k+1<len(sections) else len(block)
   # truncate at other rule directive e.g. threads/shell/run/params
   part=sec.group(2)+'\n'+block[start:end]
   lines=[]
   for line in part.splitlines():
    if re.match(r'^    (?:threads|params|shell|run|script|conda|resources|benchmark|message|priority|wrapper|group|wildcard_constraints)\s*:',line):break
    if line and not line.startswith(('        ','\t')) and line!=sec.group(2):
     if line.strip():break
    lines.append(line.strip())
   fields[sec.group(1)].extend(parse_block('\n'.join(lines)))
  rules.append({'name':m.group(2),'module':str(i),'kind':m.group(1),'inputs':fields['input'],'outputs':fields['output'],'logs':fields['log'],'source':f'workflow/rules/module{i}.smk'})

produced={}
for r in rules:
 for x in r['outputs']:
  c=canonical(x)
  if c:produced.setdefault(c,[]).append(r)
artifacts=[]; relationships=[];seen={}
for r in rules:
 for j,expr in enumerate(r['outputs']):
  c=canonical(expr);uid=hashlib.sha1((r['name']+'|'+expr).encode()).hexdigest()[:12]
  consumers=[]
  if c:
   for target in rules:
    if target['name']==r['name']:continue
    for inp in target['inputs']:
     if canonical(inp)==c:consumers.append({'rule':target['name'],'module':target['module'],'inputExpression':inp})
  unique={(v['rule'],v['module']):v for v in consumers};consumers=list(unique.values())
  cross=[v for v in consumers if v['module']!=r['module']]
  is_literal=('${' not in (c or ''))
  confidence='literal' if is_literal and c is not None else ('symbolic' if c is not None else 'unresolved')
  kind=('side' if re.search(r'log|diagnostic|report|figure|\.png|\.pdf|summary|benchmark',expr,re.I) else 'data')
  artifacts.append({'id':uid,'producer':r['name'],'producerModule':r['module'],'expression':expr,'normalized':c,'confidence':confidence,'consumers':consumers,'crossModuleConsumers':cross,'roleHint':kind,'terminalStatus':'known-unconsumed-in-declarations' if not consumers and confidence=='literal' else ('unknown-or-terminal' if not consumers else 'consumed-in-declarations')})

manifest={'schemaVersion':1,'evidence':'Static analysis of rule input/output/log declarations. Symbolic path matches are not proof of executed DAG edges. Dynamic input functions and checkpoints remain unresolved.','rules':rules,'artifacts':artifacts,'counts':{'rules':len(rules),'outputs':len(artifacts),'literalMatches':sum(bool(a['consumers']) and a['confidence']=='literal' for a in artifacts),'symbolicMatches':sum(bool(a['consumers']) and a['confidence']=='symbolic' for a in artifacts),'unresolvedOutputs':sum(a['confidence']=='unresolved' for a in artifacts)}}
(Path(__file__).resolve().parents[1]/'src'/'dependency-evidence.json').write_text(json.dumps(manifest,indent=2)+'\n')

print(manifest["counts"])
