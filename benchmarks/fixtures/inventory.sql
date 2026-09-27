CREATE TABLE warehouses(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT, warehouse_id INTEGER REFERENCES warehouses(id), quantity REAL);
INSERT INTO warehouses VALUES (1,'North'),(2,'South'),(3,'Empty');
INSERT INTO items VALUES (1,'Alpha',1,10),(2,'Beta',1,20),(3,'Gamma',2,30),(4,'Delta',2,20),(5,NULL,NULL,NULL);
