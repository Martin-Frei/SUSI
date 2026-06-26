import csv
csv.field_size_limit(10_000_000)

CSV = r"tools/evaluation/results/eval_20260624_1141_full_ragas_20260625_0842_ragas_20260626_2136.csv"

with open(CSV, encoding="utf-8") as f:
    zeilen = list(csv.DictReader(f))

final_gesetzt = [z for z in zeilen if z.get("final_score","").strip() not in ("","None")]
kein_score    = [z for z in zeilen if z.get("final_score","").strip() in ("","None")
                 and z.get("score_manuell","").strip() not in ("0","1","2")
                 and z.get("auto_score","").strip() in ("","None","0")]

print(f"Gesamt:              {len(zeilen)}")
print(f"final_score gesetzt: {len(final_gesetzt)}")
print(f"Kein Score:          {len(kein_score)}")

if final_gesetzt:
    b = final_gesetzt[0]
    print(f"\nBeispiel final_score Eintrag:")
    print(f"  auto_score:    [{b.get('auto_score')}]")
    print(f"  score_manuell: [{b.get('score_manuell')}]")
    print(f"  final_score:   [{b.get('final_score')}]")
    print(f"  bewertung_quelle: [{b.get('bewertung_quelle')}]")
    