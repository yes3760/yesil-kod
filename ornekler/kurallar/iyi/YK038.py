def ada_gore_ara(db, parca):
    # musteri_ara: CREATE VIRTUAL TABLE musteri_ara USING fts5(ad, tokenize='trigram')
    ifade = '"' + parca.replace('"', '""') + '"'
    return db.execute("SELECT rowid, ad FROM musteri_ara WHERE musteri_ara MATCH ? ORDER BY rowid", (ifade,)).fetchall()
