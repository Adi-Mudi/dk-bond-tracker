from flask import Flask, render_template


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    @app.route("/")
    def index():
        return render_template("base.html")

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
