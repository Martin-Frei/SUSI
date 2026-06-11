import json

with open('testfragen_big_run.json', encoding='utf-8') as f:
    data = json.load(f)

fixes = {
    'susi_dsgvo_03': ('lernen', 'lernen/ai/ki_deployment_tco.md'),
    'susi_dsgvo_04': ('lernen', 'lernen/ai/ki_deployment_tco.md'),
    'susi_dsgvo_05': ('lernen', 'lernen/ai/dsgvo_ki.md'),
    'proj_spv2_arch_03': ('projekte', 'coding/stockpredict/spv2_architektur.md'),
    'proj_spv2_arch_04': ('projekte', 'coding/stockpredict/spv2_architektur.md'),
}

for f in data['full_run']['fragen']:
    fid = f.get('id')
    if fid in fixes:
        kat, quelle = fixes[fid]
        f['kategorie'] = kat
        f['quelle'] = quelle
        print('Korrigiert:', fid, '->', kat, '|', quelle)

with open('testfragen_big_run.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Fertig')