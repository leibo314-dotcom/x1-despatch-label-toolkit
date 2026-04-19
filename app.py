import os

from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__, template_folder="templates", static_folder=None)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "x1-despatch-label-local")


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/generate")
def generate():
    uploaded_file = request.files.get("pdf_file")
    if not uploaded_file or not uploaded_file.filename:
        flash("Please choose a PDF file first.")
    else:
        flash("The web interface is live. PDF generation is being reconnected next.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
