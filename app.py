import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from paths import BASE_DIR, DB_PATH, UPLOAD_DIR
from pipeline import REQUIRED_COLUMNS, process_data
from visualizations import build_summary, get_analysis_snapshot, get_data

UPLOAD_FOLDER = UPLOAD_DIR

app = Flask(
    __name__,
    template_folder=BASE_DIR,
    static_folder=BASE_DIR,
    static_url_path="/static",
)
app.secret_key = "super_secret_strategic_key"

ALLOWED_EXTENSIONS = {"csv"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file was included in the request.")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("Choose a CSV file before submitting.")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file format. Upload a CSV file.")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        try:
            process_data(filepath)
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.url)
        except Exception:
            flash("The dataset could not be processed. Verify the schema and try again.")
            return redirect(request.url)

        flash(f"{filename} was uploaded and processed successfully.")
        return redirect(url_for("dashboard"))

    return render_template("upload.html", required_columns=REQUIRED_COLUMNS)


@app.route("/overview")
def overview():
    try:
        conn = get_db_connection()
        data = conn.execute("SELECT * FROM retail_sales LIMIT 100").fetchall()
        total_records = conn.execute("SELECT COUNT(*) FROM retail_sales").fetchone()[0]
        conn.close()

        columns = data[0].keys() if data else []
        summary = build_summary(get_data())
        return render_template(
            "overview.html",
            data=data,
            columns=columns,
            total_records=total_records,
            summary=summary,
        )
    except sqlite3.OperationalError:
        flash("Database not found or empty. Please upload a dataset first.")
        return redirect(url_for("upload_file"))


@app.route("/dashboard")
def dashboard():
    snapshot = get_analysis_snapshot()
    if snapshot is None:
        flash("Run the data pipeline first to generate the dashboard.")
        return redirect(url_for("upload_file"))
    return render_template(
        "dashboard.html",
        charts=snapshot["charts"],
        summary=snapshot["summary"],
    )


@app.route("/story")
def story():
    snapshot = get_analysis_snapshot()
    if snapshot is None:
        flash("Run the data pipeline first to generate the story.")
        return redirect(url_for("upload_file"))
    return render_template(
        "story.html",
        charts=snapshot["charts"],
        summary=snapshot["summary"],
    )


@app.route("/insights")
def insights():
    snapshot = get_analysis_snapshot()
    if snapshot is None:
        flash("Run the data pipeline first to generate the insights.")
        return redirect(url_for("upload_file"))
    return render_template("insights.html", summary=snapshot["summary"])


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
