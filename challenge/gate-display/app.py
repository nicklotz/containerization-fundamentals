"""gate-display: shows the departure gate of each flight at the hub.

Run it with gunicorn:

    gunicorn --bind 0.0.0.0:8000 app:app
"""

import json
from pathlib import Path

from flask import Flask, jsonify, render_template_string

GATES_FILE = Path(__file__).with_name("gates.json")

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Departure gates at {{ hub }}</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; }
    table { border-collapse: collapse; }
    th, td { padding: 0.4rem 1rem; border-bottom: 1px solid #ddd; text-align: left; }
  </style>
</head>
<body>
  <h1>Departure gates at {{ hub }}</h1>
  <table>
    <tr><th>Flight</th><th>Destination</th><th>Gate</th><th>Departs</th><th>Status</th></tr>
    {% for gate in gates %}
    <tr><td>{{ gate.flight }}</td><td>{{ gate.destination }}</td><td>{{ gate.gate }}</td><td>{{ gate.departs }}</td><td>{{ gate.status }}</td></tr>
    {% endfor %}
  </table>
</body>
</html>
"""

app = Flask(__name__)


def load_gates() -> dict:
    """Read the hub code and the list of gates from gates.json."""
    with GATES_FILE.open(encoding="utf-8") as file:
        return json.load(file)


@app.get("/")
def index():
    data = load_gates()
    return render_template_string(PAGE, hub=data["hub"], gates=data["gates"])


@app.get("/api/gates")
def api_gates():
    return jsonify(load_gates())


@app.get("/health")
def health():
    return "ok\n", 200, {"Content-Type": "text/plain; charset=utf-8"}
