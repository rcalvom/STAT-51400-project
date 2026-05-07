# Report Folder

This folder contains the manuscript draft, the compiled PDF, and the artifacts used to build the report.

## Main files

- `template.tex`: report version aligned to the provided class template
- `template.pdf`: compiled PDF for the template-aligned report
- `sample.bib`: bibliography file used by `template.tex`
- `llm_doe_final_report.tex`: editable LaTeX manuscript
- `llm_doe_final_report.pdf`: compiled PDF snapshot
- `llm_doe_submission_10page.tex`: condensed submission version capped below 10 pages
- `llm_doe_submission_10page.pdf`: compiled submission PDF
- `llm_doe_first_draft.md`: earlier narrative draft used as source material

## Supporting material

- `assets/`: figures used in the LaTeX report
- `tables/`: CSV tables and `r_session_info.txt`
- `../analysis/generate_report_artifacts.R`: script that regenerates the report-side tables and figures from `outputs/results.csv`

## Rebuild workflow

From the project root:

```bash
Rscript analysis/generate_report_artifacts.R
TEXMFVAR=/tmp/texmf-var pdflatex -interaction=nonstopmode -halt-on-error report/llm_doe_final_report.tex
TEXMFVAR=/tmp/texmf-var pdflatex -interaction=nonstopmode -halt-on-error report/llm_doe_final_report.tex
```

For the 10-page submission version:

```bash
TEXMFVAR=/tmp/texmf-var pdflatex -interaction=nonstopmode -halt-on-error report/llm_doe_submission_10page.tex
TEXMFVAR=/tmp/texmf-var pdflatex -interaction=nonstopmode -halt-on-error report/llm_doe_submission_10page.tex
```

For the template-aligned version, compile from inside `report/`:

```bash
cd report
TEXMFVAR=/tmp/texmf-var pdflatex -interaction=nonstopmode -halt-on-error template.tex
bibtex template
TEXMFVAR=/tmp/texmf-var pdflatex -interaction=nonstopmode -halt-on-error template.tex
TEXMFVAR=/tmp/texmf-var pdflatex -interaction=nonstopmode -halt-on-error template.tex
```

The temporary `TEXMFVAR` is only needed on systems where the default TeX font cache is not writable.

## Repository URL

- Repository: `https://github.com/rcalvom/STAT-51400-project`
- Manuscript commit used for this report draft: `8b76d1e`
