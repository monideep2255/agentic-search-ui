"""Adversary probe: singular-to-plural and one-case-to-general widenings, develop vs branch. No model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_removed as s

CASES = [
    ("In a patient with lupus, the drug caused liver failure.", "In patients with lupus, the drug caused liver failure"),
    ("One study found that the supplement reduced migraine frequency.", "Studies found that the supplement reduced migraine frequency"),
    ("In one family, the variant segregated with deafness.", "In families, the variant segregated with deafness"),
    ("A single case of hepatitis was reported after vaccination.", "Cases of hepatitis were reported after vaccination"),
    ("In a mouse model, the gene deletion caused tumors.", "In mouse models, the gene deletion caused tumors"),
]
for q, sent in CASES:
    print("Q:", q)
    print("S:", sent)
    print("   develop:", s.old.check_phrases(sent, [q]))
    print("   branch :", s.new.check_phrases(sent, [q]))
