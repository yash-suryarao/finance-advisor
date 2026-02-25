import sqlite3

conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()

try:
    c.execute('''
    CREATE TABLE "transactions_category_fixed" (
        "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
        "name" varchar(100) NOT NULL, 
        "user_id" char(32) NOT NULL REFERENCES "users_user" ("id") DEFERRABLE INITIALLY DEFERRED, 
        CONSTRAINT "transactions_category_user_id_name_9f02c617_uniq" UNIQUE ("user_id", "name")
    )
    ''')
    
    # The current transactions_category has columns in order: id, user_id (wrong string), name (wrong uuid)
    # We will insert them into the correct columns.
    c.execute('INSERT INTO "transactions_category_fixed" (id, name, user_id) SELECT id, user_id, name FROM "transactions_category"')
    c.execute('DROP TABLE "transactions_category"')
    c.execute('ALTER TABLE "transactions_category_fixed" RENAME TO "transactions_category"')
    
    conn.commit()
    print('SQLite Category Repair Complete!')
except Exception as e:
    conn.rollback()
    print('Error:', e)
finally:
    conn.close()
