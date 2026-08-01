# ITR Tally

Cross-checks your tax-portal capital-gains export (**MainSheet**) against your
broker's **LTCG** and **STCG** reports, fuzzy-matching company names across
the three sheets, tallying sale amounts (and unit counts for LTCG), and
fetching the purchase date/cost for every row - with full traceability of
which broker rows produced each value.

Runs entirely on your machine. Nothing is uploaded anywhere; uploaded files
are processed in a temp folder and deleted as soon as the report is built.

## Windows quick start (one click)

**Only Python is required.** Git is optional - it just lets `run.bat`
auto-pull updates for you.

1. Get the code, either way:
   - **Easiest, no Git needed:** on this repo's GitHub page, click the green
     **Code** button → **Download ZIP** → extract it anywhere.
   - **Or, if you have [Git for Windows](https://git-scm.com/download/win):**
     `git clone` the repo instead - then `run.bat` can auto-update itself on
     every run.
2. Install [Python](https://www.python.org/downloads/) (check **"Add
   python.exe to PATH"** during install).
3. Double-click **`run.bat`** inside the folder.

**On Windows 7? See the [Windows 7](#windows-7-important) section below
instead** - the latest Python download no longer installs on Windows 7.

`run.bat` sets up the virtual environment, installs everything it needs,
starts the app, and opens your browser to it automatically. Re-run it any
time - it's safe to run repeatedly. If you used the ZIP option, "updating"
just means downloading a fresh ZIP later and re-extracting over the folder.

### Windows 7 (important)

Windows 7 has been out of support from Microsoft since January 2020, and
Python has since dropped support for it too - the normal Python download
above will give you an installer that **won't run** on Windows 7. Use this
specific older version instead (still official, just not the newest):

- **Python 3.8.10** - the last python.org release with a Windows installer
  that supports Windows 7.
  [Download here](https://www.python.org/downloads/release/python-3810/)
  (pick "Windows installer (64-bit)" for a normal 64-bit PC). During setup,
  still check **"Add python.exe to PATH"**.

If you'd rather use Git than download a ZIP, Git for Windows has also
dropped Windows 7 support - use
[Git for Windows 2.46.2](https://github.com/git-for-windows/git/releases/tag/v2.46.2.windows.1)
(the `Git-2.46.2-64-bit.exe` asset) instead of the latest download. Simplest
is still to skip Git entirely and use the ZIP option above.

After that, the steps are identical: get the code and double-click
`run.bat`. `requirements.txt` is written to work with Python 3.8 as well as
modern Python, so no other changes are needed.

## Manual setup (macOS/Linux, or if you prefer running it yourself)

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open **http://127.0.0.1:5050** in your browser, upload your three
`.xls`/`.xlsx` files (MainSheet, LTCG, STCG), and click "Run tally".

## What it does

For every transaction row in MainSheet:

1. **Matches the company name** against the broker sheet (LTCG for
   Long-Term rows, STCG for Short-Term rows) using fuzzy matching, since the
   two sources spell names differently (e.g. `IPCA LABORATORIES LIMITED#NEW
   EQUITY SHARES...` vs `IPCA LABORATORIES LTD.`).
2. **Handles multi-row companies.** A company can appear as several MainSheet
   rows and many more broker rows (e.g. 5 MainSheet rows vs 27 broker rows
   for the same company). The app tries to find an exact split of the
   broker rows into groups whose sums match each MainSheet row exactly; if
   no exact split exists (common - broker vs. tax-portal amounts often
   differ by small rounding), it falls back to a best-effort grouping and
   flags it for manual review.
3. **Tallies and flags deltas.** Sale amount (and units, for LTCG) are
   compared exactly - any difference is shown as a delta (Δ) rather than
   silently ignored, so you can judge whether it's a rounding artifact or a
   real problem.
4. **Fetches purchase date/cost** from the matched broker row(s) and shows
   exactly which broker row(s) (by Excel row number) they came from, via the
   "Show broker rows" expander on each result row.

## Status colors

- **Clean** - amounts (and units) match exactly.
- **Mismatch** - company and rows matched, but the amount/units differ.
- **Approx** - this company had multiple MainSheet rows; an exact split of
  the broker rows wasn't found, so a best-effort grouping is shown - review
  it manually.
- **Unmatched** - no broker row could be matched to this company at all, or
  a MainSheet row got zero broker rows assigned during grouping.

## Project layout

```
run.bat             Windows one-click launcher (git pull, venv, install, run)
app.py              Flask app (upload + results routes)
tally/
  mainsheet.py       MainSheet parser
  ltcg.py            LTCG broker-report parser
  stcg.py            STCG broker-report parser
  name_match.py       Fuzzy company-name matching
  grouping.py         Multi-row subset-sum grouping engine
  engine.py           Orchestrates the above into per-row results
templates/, static/  Results UI
```

Your actual spreadsheet files are never committed to git (see `.gitignore`) -
they contain personal financial data.
