from flask import Flask

app = Flask(__name__)


@app.get("/")
def index():
    return "X1 despatch label toolkit is live."


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
