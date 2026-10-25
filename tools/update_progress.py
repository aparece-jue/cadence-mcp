"""Generate public progress from the original required acceptance gates only."""
import argparse,collections,hashlib,json,re
from pathlib import Path

LABELS={'passed':'完整验收通过','baseline_passed':'基础通过，待联合复验','implemented_partial':'部分实现','deferred':'存在未通过项，已后移','planned':'待实施/总验收','failed':'验收失败','waiting_dependency':'等待依赖','unverified':'尚未验证'}
EXPECTED={f'{prefix}{i:02}' for prefix,start,end in [('C',0,5),('L',1,5),('E',1,4),('D',1,5),('H',1,4),('V',1,4),('P',1,5),('A',1,1)] for i in range(start,end+1)}

def outputs(root):
    data=json.loads((root/'docs/implementation/cadence-acceptance.json').read_text(encoding='utf-8'))
    rows=[f for f in data['features'] if f.get('required') is True]
    if len(rows)!=len(EXPECTED) or {f['id'] for f in rows}!=EXPECTED or any(f['status'] not in LABELS for f in rows):
        raise ValueError('Required scope/status changed; review the original34 gates before changing the denominator.')
    counts=collections.Counter(f['status'] for f in rows);total=len(rows);done=counts['passed'];percent=round(100*done/total,1)
    groups={}
    for name,selected in [('Capture',[f for f in rows if f['id'][0] not in ('P','A')]),('PSpice',[f for f in rows if f['id'].startswith('P')]),('最终联合验收',[f for f in rows if f['id'].startswith('A')])]:
        passed=sum(f['status']=='passed' for f in selected);groups[name]={'passed':passed,'total':len(selected),'percent':round(100*passed/len(selected),1)}
    fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    regression=data['lastBatch']['latestFullRegression']
    summary={'asOf':data['date'],'metric':'required_gates_fully_accepted','passed':done,'total':total,'percent':percent,'remaining':total-done,'statusCounts':{k:counts[k] for k in LABELS},'groups':groups,'toolCount':data['lastBatch']['tools'],'latestFullRegression':regression,'acceptanceCanonicalSha256':fingerprint}
    lines=['# 研发进度','','![完整验收进度](progress.svg)','',f'更新依据：验收清单 {data["date"]}。**完整验收：{done}/{total}（{percent:.1f}%）；仍需完成{total-done}项。**','',
           '只将原34项必需子目标中状态为`passed`的项计入完成。基础通过、部分实现、失败后移和权限跳过均不折算成完成；各项工作量不同，这不是工时消耗比例。','',
           '| 范围 | 完整通过 / 总数 | 完整验收率 |','|---|---:|---:|']
    lines += [f'| {name} | {g["passed"]}/{g["total"]} | {g["percent"]:.1f}% |' for name,g in groups.items()]
    lines += ['','| 状态 | 项数 |','|---|---:|']+[f'| {LABELS[k]} | {counts[k]} |' for k in LABELS if counts[k]]
    lines += ['',f'当前工具数：{summary["toolCount"]}。最近完整回归：{regression["total"]}项，{regression["passed"]}通过、{regression["skipped"]}跳过；测试通过率不作为业务完成度。','',
              '[最新批次与下一步](implementation/CURRENT-STATE.md) · [原实施/验收计划](implementation/cadence-plan.md) · [原始验收清单与问题](implementation/cadence-acceptance.json) · [参考资料索引](references/INDEX.md) · [研发与Git同步规则](DEVELOPMENT.md)','',
              '| 子目标 | 功能 | 当前状态 |','|---|---|---|']
    esc=lambda s:str(s).replace('|','\\|').replace('\n',' ')
    lines += [f'| {f["id"]} | {esc(f["title"])} | {LABELS[f["status"]]} |' for f in rows]
    lines += ['','本页、进度图、JSON及参考索引由`python tools/update_progress.py`生成；`--check`检查是否与清单一致。功能范围变更必须先明确更新计划，不能通过减少分母提高完成率。','']
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="65" viewBox="0 0 400 65" role="img" aria-label="完整验收{done}/{total}，{percent:.1f}%">
<title>完整验收：{done}/{total}（{percent:.1f}%）</title>
<rect width="400" height="65" rx="8" fill="#f1f5f9"/>
<text x="14" y="24" font-family="sans-serif" font-size="15" fill="#0f172a">完整验收 {done}/{total} · {percent:.1f}%</text>
<rect x="14" y="36" width="372" height="12" rx="6" fill="#cbd5e1"/>
<rect x="14" y="36" width="{372*done/total:.3f}" height="12" rx="6" fill="#2563eb"/>
</svg>
'''
    refs=['# 参考资料索引','','官方资料以安装内原件为依据；下表只公开文件定位、用途与SHA256指纹，不上传Cadence手册全文、安装二进制、许可证或真实工程。相对路径从所配置的Cadence安装根目录开始。','',
          '[本机核查与原创研究笔记](../design/01-local-findings.md) · [架构与工具契约设计](../design/README.md) · [实施与验收计划](../implementation/cadence-plan.md) · [完整资料元数据](../implementation/cadence-acceptance.json)','',
          '| 来源ID | 用途 | 安装内相对路径 | SHA256前12位 |','|---|---|---|---|']
    refs += [f'| {esc(s["sourceId"])} | {esc(s["meaning"])} | `{esc(s["installRelativePath"])}` | `{s["sha256"][:12]}` |' for s in data['sources']]
    refs += ['','完整SHA256与文件大小见原始验收清单。原创最小复现与可再分发材料可随源码提交；第三方资料有明确再分发许可后才纳入。私有原生输出留在`.local`，公开其脱敏结论、复现步骤及摘要。','']
    readme=(root/'README.md').read_text(encoding='utf-8')
    block=f'<!-- progress:start -->\n\n[![完整验收进度](docs/progress.svg)](docs/PROGRESS.md)\n\n[当前进度：{done}/{total}（{percent:.1f}%）](docs/PROGRESS.md) · [研发同步规则](docs/DEVELOPMENT.md) · [参考资料](docs/references/INDEX.md)\n\n<!-- progress:end -->'
    if '<!-- progress:start -->' in readme:
        if readme.count('<!-- progress:start -->')!=1 or readme.count('<!-- progress:end -->')!=1:raise ValueError('Ambiguous README progress block')
        readme=re.sub(r'<!-- progress:start -->.*?<!-- progress:end -->',lambda _:block,readme,flags=re.S)
    else:
        if not readme.startswith('# cadence-mcp\n'):raise ValueError('Missing README heading')
        readme=readme.replace('# cadence-mcp\n','# cadence-mcp\n\n'+block+'\n',1)
    return {'docs/PROGRESS.md':'\n'.join(lines),'docs/progress.svg':svg,'docs/progress.json':json.dumps(summary,ensure_ascii=False,indent=2)+'\n','docs/references/INDEX.md':'\n'.join(refs),'README.md':readme},summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args();root=Path(__file__).resolve().parents[1];files,summary=outputs(root);stale=[]
    for rel,content in files.items():
        path=root/rel
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8')!=content:stale.append(rel)
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
    if stale:raise SystemExit('Outdated generated progress: '+', '.join(stale))
    print(f'Full acceptance: {summary["passed"]}/{summary["total"]} ({summary["percent"]:.1f}%); remaining {summary["remaining"]}; '+('current' if args.check else 'generated'))

if __name__=='__main__':main()
