"""Extract module-level documentation snapshot from an unpacked IBP repository.
Usage: python tools/extract_pipeline.py C:/path/to/Integrated-Bioinformatics-Project
"""
import ast
import json
import re
import sys
from pathlib import Path

LABELS = [
 ('Assembly discovery & selection','Discover, filter and select assemblies from public metadata.'),
 ('Download & quality control','Download genome data and assess assembly quality.'),
 ('Chromosome normalization','Determine topology and normalize accepted chromosomes.'),
 ('Reference & preparation','Select species references and prepare comparison packages.'),
 ('Inversion calling','Plan genome comparisons and run inversion detection.'),
 ('Inversion catalogue','Consolidate candidate inversion events.'),
 ('Cross-species aggregation','Aggregate inversion results across studied species.'),
 ('Agreement & analysis','Evaluate caller agreement and produce final analyses.'),
]

def extract(root):
    out=[]
    for i,(title,description) in enumerate(LABELS,1):
        smk=Path('workflow/rules') / f'module{i}.smk'
        raw=(root/smk).read_text(encoding='utf-8') if (root/smk).exists() else ''
        rule_names=re.findall(r'^\s*(?:rule|checkpoint)\s+([A-Za-z_]\w*)\s*:',raw,re.M)
        scripts=[]
        for file in sorted((root/'src'/'ibp'/f'module{i}').glob('*.py')):
            if file.name == '__init__.py':continue
            summary=''
            try:summary=ast.get_docstring(ast.parse(file.read_text(encoding='utf-8'))) or ''
            except (SyntaxError,UnicodeError):pass
            scripts.append({'name':file.name,'path':file.relative_to(root).as_posix(),'description':summary.split('\n\n')[0][:400]})
        out.append({'id':str(i),'title':title,'description':description,'ruleFile':smk.as_posix(),
                    'rules':rule_names,'scripts':scripts,'sourcePresent':bool(raw)})
    return {'project':root.name,'modules':out,'graphKind':'conceptual-module-overview',
            'notice':'Connections illustrate scientific stage progression, not resolved Snakemake job dependencies.'}

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python tools/extract_pipeline.py PATH_TO_IBP_REPOSITORY')
    root=Path(sys.argv[1]).expanduser().resolve()
    if not (root/'Snakefile').is_file():raise SystemExit(f'Snakefile not found in: {root}')
    dest=Path(__file__).resolve().parents[1]/'src'/'pipeline.json'
    dest.write_text(json.dumps(extract(root),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'Wrote {dest} from {root}')
