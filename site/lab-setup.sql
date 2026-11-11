-- FOCUS SQL Lab: everything the lab adds to DuckDB before you run a query.
--
-- The specification's example queries run exactly as published. Nothing here changes a query: each statement
-- supplies a name or function that the queries expect and DuckDB doesn't have.
--
-- The specification writes its queries in ANSI SQL, using BigQuery's JSON functions where it reads JSON,
-- because ANSI SQL has no JSON functions. It says those may need adapting for other database engines.
-- The first four statements give DuckDB those BigQuery names, with BigQuery's behaviour.

-- BigQuery's JSON_VALUE returns a JSON value as plain text. DuckDB's own json_value keeps the JSON quote marks
-- ("Input" rather than Input), so a test such as = 'Input' would never match.
--
-- It also has to handle one more difference. In BigQuery, FROM ... CROSS JOIN UNNEST(array) AS x names each
-- element x. In the DuckDB version this page runs (1.5), x names a row that holds the element in a field called
-- unnest. So when json_value is given such a row, it reads from that field.
CREATE OR REPLACE MACRO json_value(j, p := '$') AS
  CASE WHEN typeof(j) LIKE 'STRUCT(%unnest%' THEN json_extract_string(CAST(j AS JSON), '$.unnest' || substr(p, 2))
       ELSE json_extract_string(j, p) END;

-- BigQuery's JSON_EXTRACT_ARRAY returns the elements of a JSON array, for UNNEST to turn into rows.
CREATE OR REPLACE MACRO json_extract_array(j, p := '$') AS CAST(json_extract(j, p) AS JSON[]);

-- BigQuery's JSON_VALUE_ARRAY returns the values of a JSON array as plain text. It handles UNNEST rows the same way
-- as json_value.
CREATE OR REPLACE MACRO json_value_array(j, p := '$') AS
  CASE WHEN typeof(j) LIKE 'STRUCT(%unnest%' THEN json_extract_string(CAST(j AS JSON), '$.unnest' || substr(p, 2) || '[*]')
       ELSE json_extract_string(j, p || '[*]') END;

-- BigQuery's name for a 64-bit floating-point number, used in CAST(... AS FLOAT64).
CREATE TYPE FLOAT64 AS DOUBLE;

-- The version migration guide's six example queries read from a table called focus_data, which the guide doesn't
-- define. It stands for your Cost and Usage table.
CREATE OR REPLACE VIEW focus_data AS SELECT * FROM CostAndUsage;
