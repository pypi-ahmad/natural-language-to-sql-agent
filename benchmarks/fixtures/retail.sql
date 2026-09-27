CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE orders(id INTEGER PRIMARY KEY, status TEXT, customer_id INTEGER REFERENCES customers(id), total REAL);
INSERT INTO customers VALUES (1,'North'),(2,'South'),(3,'Empty');
INSERT INTO orders VALUES (1,'Alpha',1,10),(2,'Beta',1,20),(3,'Gamma',2,30),(4,'Delta',2,20),(5,NULL,NULL,NULL);
