def ada_gore_ara(db, parca):
    return db.execute("SELECT id, ad FROM musteri WHERE ad LIKE '%' || ? || '%'", (parca,)).fetchall()
