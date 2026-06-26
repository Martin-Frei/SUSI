import csv
import sys
sys.path.insert(0, "tools/evaluation")
from analyse_csv import get_effektiver_score, AUTO_SCORE_MAPPING

csv.field_size_limit(10_000_000)

CSV = r"tools/evaluation/results/eval_20260624_1141_full_ragas_20260625_0842_ragas_20260626_2136.csv"

with open(CSV, encoding="utf-8") as f:
    zeilen = list(csv.DictReader(f))

# Die 221 ohne Score
kein_score = [z for z in zeilen
              if z.get("final_score","").strip() in ("","None")
              and z.get("score_manuell","").strip() not in ("0","1","2")
              and z.get("auto_score","").strip() in ("","None","0")]

nur_auto = [z for z in zeilen
            if z.get("final_score","").strip() in ("","None")
            and z.get("score_manuell","").strip() not in ("0","1","2")
            and z.get("auto_score","").strip() not in ("","None")]

print(f"Kein Score (auto=leer):  {len(kein_score)}")
print(f"Nur auto_score gesetzt:  {len(nur_auto)}")

if nur_auto:
    b = nur_auto[0]
    auto = b.get("auto_score","").strip()
    manuell = b.get("score_manuell","").strip()
    final = b.get("final_score","").strip()
    print(f"\nBeispiel:")
    print(f"  auto_score:    [{auto}]")
    print(f"  score_manuell: [{manuell}]")
    print(f"  final_score:   [{final}]")
    print(f"  get_effektiver_score: {get_effektiver_score(b)}")
    print(f"  auto in MAPPING: {auto in AUTO_SCORE_MAPPING}")