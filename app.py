"""Local web app: upload MainSheet/LTCG/STCG excel files, run the tally
engine, and show a clean, readable report of matches/mismatches with full
traceability of where every fetched value (date, cost) came from.

Run with:  python app.py
Then open: http://127.0.0.1:5050

Set ITRTALLY_DEBUG=1 to enable Flask's debug/reload mode during development.
"""
import os
import tempfile

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from tally import engine

app = Flask(__name__)
app.secret_key = "itrtally-local-dev-only"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB per upload

ALLOWED_EXTENSIONS = {".xls", ".xlsx"}


def _allowed(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


def _display_status(row) -> str:
    """Collapse a ResultRow's grouping status + tally checks into one of
    four buckets the template colors: ok / mismatch / approx / error."""
    if row.group_status in ("no_company_match", "empty"):
        return "error"
    if row.group_status == "approx":
        return "approx"
    checks_ok = row.amount_match and (row.units_match is None or row.units_match)
    return "ok" if checks_ok else "mismatch"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    files = {
        "mainsheet": request.files.get("mainsheet"),
        "ltcg": request.files.get("ltcg"),
        "stcg": request.files.get("stcg"),
    }
    for key, f in files.items():
        if not f or f.filename == "":
            flash(f"Please choose a file for {key.upper()}.")
            return redirect(url_for("index"))
        if not _allowed(f.filename):
            flash(f"{key.upper()} must be a .xls or .xlsx file.")
            return redirect(url_for("index"))

    with tempfile.TemporaryDirectory(prefix="itrtally_") as tmpdir:
        paths = {}
        for key, f in files.items():
            path = os.path.join(tmpdir, secure_filename(f"{key}_{f.filename}"))
            f.save(path)
            paths[key] = path

        try:
            result = engine.run(paths["mainsheet"], paths["ltcg"], paths["stcg"])
        except Exception as exc:  # surface a friendly error instead of a stack trace
            flash(f"Could not process the files: {exc}")
            return redirect(url_for("index"))

    ltcg_rows = result["ltcg"]
    stcg_rows = result["stcg"]

    for r in ltcg_rows:
        r.display_status = _display_status(r)
    for r in stcg_rows:
        r.display_status = _display_status(r)

    def summarize(rows):
        return {
            "total": len(rows),
            "ok": sum(1 for r in rows if r.display_status == "ok"),
            "mismatch": sum(1 for r in rows if r.display_status == "mismatch"),
            "approx": sum(1 for r in rows if r.display_status == "approx"),
            "error": sum(1 for r in rows if r.display_status == "error"),
        }

    return render_template(
        "results.html",
        ltcg_rows=ltcg_rows,
        stcg_rows=stcg_rows,
        ltcg_summary=summarize(ltcg_rows),
        stcg_summary=summarize(stcg_rows),
    )


if __name__ == "__main__":
    debug = os.environ.get("ITRTALLY_DEBUG") == "1"
    app.run(debug=debug, port=5050)
