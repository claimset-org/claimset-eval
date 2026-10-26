# Papers

Open-access papers under licences that allow converting them and publishing the result (CC BY, CC BY-SA, CC0, and their NC variants). Nothing derived from an NC paper may go into the private converter repository.

`papers.csv` lists each paper: identifier, title, authors, licence and file. `text/` holds the extracted text of each paper, with `[pN.M]` markers (page N, paragraph M), and its metadata.

## How the texts were made

- **Pilot texts** (`text/` for the papers in `pilot/`): extracted once with PyMuPDF 1.28.2 and fixed rules (MuPDF text blocks; hyphens joined against the paper's own vocabulary; running headers, page numbers and download stamps removed; columns read left then right; short equation and table fragments appended to the paragraph before). They stay as they are, so the markers in the pilot claimsets keep pointing at the same paragraphs.
- **All later papers, including the whole confirmatory set**: extracted with `claimset-convert extract` (converter 0.7.1 or later), which applies the same rules to characters read by pdfminer.six. Its output is close to the pilot texts but not identical (equations, figure labels and tables are split or spaced differently more often), so the confirmatory set comes from one tool and is not mixed with pilot-tool texts. Record the converter version used for each paper.
