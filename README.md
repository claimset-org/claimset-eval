# claimset-eval

Hand-made claimsets of five forecasting papers, made with the paper's author, as reference conversions for developing and testing the Claimset converter.

- `papers/pilot/`: the papers (PDF); `papers/papers.csv` lists them with their licences.
- `papers/text/`: the papers' extracted text. Its `[pN.M]` markers (page N, paragraph M) are what the claimsets' `source_spans` point to.
- `claimset/pilot/`: one claimset per paper (`<paper>.claimset.json`) and its reading view (`<paper>.claimset.txt`, made by `claimset render`).
- `tools/compare.py`: compares a candidate claimset (a converter's output) with the hand-made one of the same paper, without any model: claims (one-to-one, and many-to-one to show bundled claims), the links between them, definitions, evidence with its tables and setup, limitations, references and relations. `python3 tools/compare.py claimset/pilot/X.claimset.json candidate.json --text papers/text/X.txt [--json report.json]`.
