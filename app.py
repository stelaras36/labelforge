from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
import sqlite3, json

app = FastAPI(title="LabelForge")

# --- Health
@app.get("/health")
def health():
    return {"status": "ok"}

# --- Debug: counts
@app.get("/debug/status")
def debug_status():
    con = sqlite3.connect("labelforge.db")
    try:
        cur = con.cursor()
        users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        projects = cur.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        items = cur.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        labels = cur.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
        return {"users": users, "projects": projects, "items": items, "labels": labels}
    finally:
        con.close()

# --- Debug: seed 10 demo texts (GET για ευκολία από browser)
@app.get("/debug/seed_texts")
def debug_seed_texts():
    demo_texts = [
        "Το φαγητό ήταν καταπληκτικό και το προσωπικό ευγενικό.",
        "Πολύ αργή εξυπηρέτηση, δεν θα ξαναπάω.",
        "Καλή ποιότητα αλλά ακριβό.",
        "Η ατμόσφαιρα ήταν υπέροχη και πολύ φιλική.",
        "Οι μερίδες ήταν μικρές για την τιμή.",
        "Το προσωπικό ήταν αδιάφορο και αγενές.",
        "Τα γλυκά ήταν εξαιρετικά, θα ξαναπάω σίγουρα.",
        "Η μουσική ήταν πολύ δυνατή, δεν μπορούσαμε να μιλήσουμε.",
        "Η τοποθεσία βολική και το πάρκινγκ εύκολο.",
        "Το φαγητό ήρθε κρύο στο τραπέζι."
    ]
    con = sqlite3.connect("labelforge.db")
    try:
        cur = con.cursor()
        for t in demo_texts:
            payload = json.dumps({"text": t})
            cur.execute(
                "INSERT INTO items(project_id, payload_json) VALUES(?, ?)",
                (1, payload),
            )
        con.commit()
        return {"ok": True, "inserted": len(demo_texts)}
    finally:
        con.close()

# --- Next item for labeling
@app.get("/items/next")
def items_next(user_id: int = 1, project_id: int = 1):
    con = sqlite3.connect("labelforge.db")
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        row = cur.execute(
            """
            SELECT i.id, i.payload_json
            FROM items i
            WHERE i.project_id = ?
              AND i.id NOT IN (SELECT item_id FROM labels WHERE user_id = ?)
            LIMIT 1
            """,
            (project_id, user_id),
        ).fetchone()

        if not row:
            return {"done": True}

        payload = json.loads(row["payload_json"])
        return {"done": False, "item_id": row["id"], "payload": payload}
    finally:
        con.close()

# --- Store a label (GET για δοκιμές)
@app.get("/labels/add")
def labels_add(item_id: int, label: str, user_id: int = 1):
    con = sqlite3.connect("labelforge.db")
    try:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO labels(item_id, user_id, label) VALUES(?,?,?)",
            (item_id, user_id, label),
        )
        con.commit()
        return {"ok": True, "item_id": item_id, "label": label}
    finally:
        con.close()

# --- Minimal HTML UI
@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
<!doctype html>
<meta charset="utf-8" />
<title>LabelForge — Text Labeling</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; }
  .box { border: 1px solid #ddd; padding: 16px; border-radius: 12px; }
  .choices button { margin-right: 8px; padding: 10px 14px; border-radius: 10px; border: 1px solid #ccc; cursor: pointer; }
  #text { font-size: 1.2rem; white-space: pre-wrap; }
  #status { color: #666; }
</style>

<div class="box">
  <h1>LabelForge</h1>
  <p id="status">Loading…</p>
  <blockquote id="text"></blockquote>
  <div class="choices">
    <button onclick="send('positive')">Positive (1)</button>
    <button onclick="send('neutral')">Neutral (2)</button>
    <button onclick="send('negative')">Negative (3)</button>
  </div>
</div>

<script>
const user_id = 1, project_id = 1;
let currentItem = null;

async function fetchNext() {
  const r = await fetch(`/items/next?user_id=${user_id}&project_id=${project_id}`);
  const j = await r.json();
  if (j.done) {
    currentItem = null;
    document.getElementById('status').textContent = 'All done!';
    document.getElementById('text').textContent = '';
    return;
  }
  currentItem = j.item_id;
  document.getElementById('status').textContent = `Item #${j.item_id}`;
  document.getElementById('text').textContent = j.payload.text;
}

async function send(label) {
  if (!currentItem) return;
  await fetch(`/labels/add?item_id=${currentItem}&label=${encodeURIComponent(label)}&user_id=${user_id}`);
  currentItem = null;
  fetchNext();
}

document.addEventListener('keydown', (e) => {
  if (e.key === '1') send('positive');
  if (e.key === '2') send('neutral');
  if (e.key === '3') send('negative');
});

fetchNext();
</script>
"""
@app.get("/export/csv")
def export_csv(project_id: int = 1):
    import io, csv, json, sqlite3
    con = sqlite3.connect("labelforge.db")
    try:
        cur = con.cursor()
        rows = cur.execute("""
            SELECT i.payload_json, l.label
            FROM items i
            JOIN labels l ON l.item_id = i.id
            WHERE i.project_id = ?
            ORDER BY i.id
        """, (project_id,)).fetchall()

        # Χρήση StringIO για in-memory CSV
        buf = io.StringIO(newline="")
        w = csv.writer(buf)
        w.writerow(["text", "label"])
        for payload_json, label in rows:
            text = json.loads(payload_json)["text"]
            w.writerow([text, label])

        # Προσθήκη BOM για σωστό encoding στο Excel
        csv_text = buf.getvalue()
        csv_bytes = ("\ufeff" + csv_text).encode("utf-8")

        return StreamingResponse(
            iter([csv_bytes]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=labels.csv"}
        )
    finally:
        con.close()
@app.get("/export/jsonl")
def export_jsonl(project_id: int = 1):
    import io, json, sqlite3
    con = sqlite3.connect("labelforge.db")
    try:
        cur = con.cursor()
        rows = cur.execute("""
            SELECT i.payload_json, l.label
            FROM items i
            JOIN labels l ON l.item_id = i.id
            WHERE i.project_id = ?
            ORDER BY i.id
        """, (project_id,)).fetchall()

        buf = io.StringIO()
        for payload_json, label in rows:
            text = json.loads(payload_json)["text"]
            line = json.dumps({"text": text, "label": label}, ensure_ascii=False)
            buf.write(line + "\n")
        buf.seek(0)

        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8")]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=labels.jsonl"}
        )
    finally:
        con.close()

