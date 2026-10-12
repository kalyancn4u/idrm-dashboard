"""
IDRM — application entrypoint.

    Development :  flask --app run.py run --debug
    Production  :  gunicorn -w 4 -k gthread "run:app"
"""

from __future__ import annotations

import os

from app import create_app

app = create_app(os.getenv("FLASK_ENV", "development"))


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=app.config.get("DEBUG", False),
    )
