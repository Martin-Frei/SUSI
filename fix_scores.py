
import csv

path = 'tools/evaluation/results/eval_20260715_1056_full_ragas_20260715_1131.csv'

fixes = {
    'tech_01': '2', 'tech_03': '2', 'tech_07': '2',
    'pers_03': '2', 'pers_09': '2',
    'lern_02': '2',
    'proj_02': '2', 'proj_05': '1', 'proj_07': '2', 'proj_09': '2',
}

with open(path, 'r', encoding='utf-8') as f:
    reader = list(csv.DictReader(f))
    fieldnames = reader[0].keys() if reader else []

changed = 0
for row in reader:
    fid = row.get('frage_id', '')
    if fid in fixes:
        old = row['score_manuell']
        row['score_manuell'] = fixes[fid]
        print(f"  {fid}: {old} -> {fixes[fid]}")
        changed += 1

with open(path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(reader)

print(f'\n{changed} Zeilen gefixt.')


