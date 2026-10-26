# Working on this repository

The claimsets in `claimset/pilot/` are made by hand, one paper at a time, with the paper's author deciding what each claim is. They follow the Claimset specification in the `claimset` package (`pip install git+https://github.com/claimset-org/claimset`).

- Edit claimsets freely; there is no lab record. After every change run `claimset validate` on the file and regenerate its reading view with `claimset render`.
- Every claim, evidence object and limitation has `source_spans` pointing at `[pN.M]` markers of `papers/text/`.
- Ask the author about anything uncertain, one question at a time.
- `tools/` and `tests/` use only the Python standard library; run `python3 -m unittest discover -s tests` before committing.
- Never put credentials in a file, a command line or a commit.
- The converter is proprietary (private repository `claimset-org/claimset-convert`). Never copy its instructions, prompts or code into this repository.
- Papers under non-commercial licences (`NC` in `papers/papers.csv`): nothing derived from them (text, excerpts, claimsets) ever goes into the converter repository, its instructions, tests or examples.
