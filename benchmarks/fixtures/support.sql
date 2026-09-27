CREATE TABLE teams(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE tickets(id INTEGER PRIMARY KEY, title TEXT, team_id INTEGER REFERENCES teams(id), priority REAL);
INSERT INTO teams VALUES (1,'North'),(2,'South'),(3,'Empty');
INSERT INTO tickets VALUES (1,'Alpha',1,10),(2,'Beta',1,20),(3,'Gamma',2,30),(4,'Delta',2,20),(5,NULL,NULL,NULL);
