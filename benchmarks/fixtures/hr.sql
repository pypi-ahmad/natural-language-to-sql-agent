CREATE TABLE departments(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE employees(id INTEGER PRIMARY KEY, name TEXT, department_id INTEGER REFERENCES departments(id), salary REAL);
INSERT INTO departments VALUES (1,'North'),(2,'South'),(3,'Empty');
INSERT INTO employees VALUES (1,'Alpha',1,10),(2,'Beta',1,20),(3,'Gamma',2,30),(4,'Delta',2,20),(5,NULL,NULL,NULL);
