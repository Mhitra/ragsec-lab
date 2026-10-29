// Experiment 18: a least-privilege database user for the app. UNTESTED: written from the Neo4j 5 privilege
// syntax; check every statement against the documentation of your edition and run it as an administrator.
// Needs an edition with custom roles and fine-grained privileges (Enterprise Edition, or an Aura tier that
// offers them; Aura Free does not). Run the statements one by one in the system database.
//
// Set the password first (Neo4j Browser):  :param password => 'choose-a-long-random-password'

CREATE ROLE ragreader IF NOT EXISTS;
CREATE USER ragapp IF NOT EXISTS SET PASSWORD $password CHANGE NOT REQUIRED;
GRANT ROLE ragreader TO ragapp;

// Reading: only the labels and relationship types the app is meant to see.
GRANT ACCESS ON DATABASE neo4j TO ragreader;
GRANT MATCH {*} ON GRAPH neo4j NODES Host, Container, Port TO ragreader;
GRANT MATCH {*} ON GRAPH neo4j RELATIONSHIPS RUNS, EXPOSES, DEPENDS_ON TO ragreader;

// Belt and braces: DENY wins over any grant, including one inherited from the PUBLIC role.
DENY READ {*} ON GRAPH neo4j NODES Secret TO ragreader;
DENY TRAVERSE ON GRAPH neo4j NODES Secret TO ragreader;
DENY TRAVERSE ON GRAPH neo4j RELATIONSHIPS HAS_SECRET TO ragreader;

// Hardening, added after the first run of Experiment 18. The built-in PUBLIC role, which every user has and which
// cannot be edited, grants EXECUTE PROCEDURE *, EXECUTE USER DEFINED FUNCTION * and LOAD ON ALL DATA. A DENY on
// ragreader wins over those grants. Only dangerous procedure families and schema-listing procedures are denied,
// so the app can still read its schema (apoc.meta.data and the other db.* procedures stay available).
DENY LOAD ON ALL DATA TO ragreader;
DENY EXECUTE PROCEDURE dbms.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.cypher.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.load.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.export.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.import.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.periodic.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.trigger.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.systemdb.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.custom.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.create.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.merge.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE apoc.refactor.* ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE db.labels ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE db.relationshipTypes ON DBMS TO ragreader;
DENY EXECUTE PROCEDURE db.propertyKeys ON DBMS TO ragreader;
// SHOW CURRENT USER needs no privilege and cannot be denied by a role; only a query check stops it.

// No WRITE, CREATE, DELETE, SET or SCHEMA privileges are granted, so writes fail at the database.
// Check what the user really has:
//   SHOW USER ragapp PRIVILEGES AS COMMANDS;
//   SHOW ROLE PUBLIC PRIVILEGES AS COMMANDS;
//
// If the app fails at startup while reading the schema, the user may lack EXECUTE on the schema procedures
// that LangChain's Neo4jGraph.refresh_schema() calls; read the error and grant only what it names.
