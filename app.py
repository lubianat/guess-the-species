import requests
import sqlite3
import hashlib
import json
from flask import Flask, render_template, jsonify
import re

# Initialize Flask app and SQLite database connection
app = Flask(__name__)
DATABASE = "species_cache.db"

WIKI_API = "https://query.wikidata.org/sparql"
SPARQL_QUERY = """
SELECT ?species ?speciesLabel (SAMPLE(?images) as ?image) WHERE {
  ?species wdt:P31 wd:Q16521.
  ?species wdt:P171* wd:Q5113.
  ?species wdt:P105 wd:Q7432.
  ?species wdt:P18 ?images.
  ?species wikibase:sitelinks ?links.
  ?species wdt:P225 ?speciesLabel.
  ?species wdt:P9714 wd:Q155.
  FILTER(?links > 5)
}
GROUP BY ?species ?speciesLabel
"""

def initialize_db():
    """Create the SQLite database and species table if they don't exist."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS species_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            data_hash TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()
    conn.close()

def get_species_from_wikidata():
    """Fetch species data from the Wikidata SPARQL endpoint."""
    url = f"{WIKI_API}?query={requests.utils.quote(SPARQL_QUERY)}"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers)
    data = response.json()

    species_list = [
        {
            "label": item["speciesLabel"]["value"],
             "filename" : item["image"]["value"].replace("http://commons.wikimedia.org/wiki/Special:FilePath/", "")

        }
        for item in data["results"]["bindings"]
    ]
    return species_list


def save_species_to_db(species_list):
    """Save the species data and its hash to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    data = json.dumps(species_list)
    data_hash = hashlib.sha256(data.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO species_cache (data, data_hash) VALUES (?, ?)", (data, data_hash))
    conn.commit()
    conn.close()

def get_cached_species():
    """Retrieve cached species data from the database if available."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT data FROM species_cache ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

@app.route('/species')
def species():
    """API route to serve species data, using cache if available."""
    cached_data = get_cached_species()
    if cached_data:
        return jsonify(cached_data)

    # If no cache, fetch data from Wikidata and store in the database
    species_data = get_species_from_wikidata()
    save_species_to_db(species_data)
    return jsonify(species_data)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    initialize_db()
    app.run(debug=True)
