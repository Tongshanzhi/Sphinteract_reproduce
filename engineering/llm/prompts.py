SRA = """/* Ask the user a new multiple choice clarification question to help you find the correct SQL answer for the following question: */
{question}
/* Given the following database schema: */
{schema}
/* And the following incorrect sql answers: */
{sqls}
/* And the following previous clarification questions and user replies: */
{cqs}

/* Consider the following ambiguity categories:
    - AmbQuestion: Is the question itself ambiguous?
    - AmbTableColumn: Is there ambiguity in mapping the entities from the QUESTION to tables and columns in the DATABASE SCHEMA?
    - AmbOutput: What fields and how many fields should be included in the output table?
    - AmbValue: What predicate value should be used to filter results?
*/

/* The clarification question should be easy to understand for people with no coding experience. */

/* Let's think step by step to generate the helpful multiple choice clarification question.
1. Summarize the clear information based on previous clarification questions and incorrect queries.
2. Evaluate whether AmbQuestion, AmbTableColumn, AmbOutput, and AmbValue remain in formulating an SQL query, considering each category individually.
3. Ask a new multiple-choice question to address the remaining ambiguities and assist in identifying the correct SQL query. Use format: mul_choice_cq = "".
4. Prioritize granularity alignment and valid join keys; avoid suggesting joins across incompatible levels (e.g., district vs state) or metrics that cannot be computed at a common grain.
*/
"""

SRA_ES = """/* Ask the user a new multiple choice clarification question to help you find the correct SQL answer for the following question: */
{question}
/* Given the following database schema: */
{schema}
/* And the following incorrect sql answers: */
{sqls}
/* And the following previous clarification questions and user replies: */
{cqs}

/* Consider the following ambiguity categories:
    - AmbQuestion: Is the question itself ambiguous?
    - AmbTableColumn: Is there ambiguity in mapping the entities from the QUESTION to tables and columns in the DATABASE SCHEMA?
    - AmbOutput: What fields and how many fields should be included in the output table?
    - AmbValue: What predicate value should be used to filter results?
*/

/* The clarification question should be easy to understand for people with no coding experience. */

/* Let's think step by step to generate the helpful multiple choice clarification question.
1. Summarize the clear information based on previous clarification questions and incorrect queries.
2. Evaluate whether AmbQuestion, AmbTableColumn, AmbOutput, and AmbValue remain in formulating an SQL query, considering each category individually.
3. If no remaining ambiguities are identified, then output "NO AMBIGUITY".
   Else, ask a new multiple-choice question to address the remaining ambiguities and assist in identifying the correct SQL query. Use format: mul_choice_cq = "".
4. Prioritize granularity alignment and valid join keys; avoid suggesting joins across incompatible levels (e.g., district vs state) or metrics that cannot be computed at a common grain.
*/
"""

sql_generation_v2 = """/* Given the following database schema: */
{schema}
/* And the following incorrect sql answers: */
{sqls}
/* And the following user replies to help you write the correct sql query: */
{cqas}

{metadata}
/* Answer the following with no explanation: {question} */
/* Output ONLY SQL wrapped in a markdown block: ```sql */
"""

fix_invalid_v1 = """/* Given the following database schema: */
{schema}
/* And the following inexecutable sql query */
{invalidSQL}
/* And the following exception message */
{ex}

/* Fix the exception and write a new executable SQL query with no explanation */
/* Output ONLY SQL wrapped in a markdown block: ```sql */
"""

sql_generation_selfdebug = """/* Given the following database schema: */
{schema}
/* And the following incorrect sql answers: */
{sqls}

{metadata}
/* Answer the following with no explanation: {question} */
/* Output ONLY SQL wrapped in a markdown block: ```sql */
"""

def build_metadata_constraints(nlq, schema):
    s_lower = schema.lower()
    n_lower = nlq.lower()
    cons = []
    cons.append("Constraints: SQL must be executable on the given schema and use a single consistent granularity across tables.")
    cons.append("When tables differ in granularity, aggregate to a common key before joining; do not join district/school rows directly to state-level aggregates.")
    cons.append("Use only valid join keys present in the schema with matching types; prefer exact equality joins.")
    cons.append("If feedback conflicts with these constraints, follow the constraints.")
    #if ("finrev_fed_17" in s_lower) and ("ndecorexcel_math_grade8" in s_lower):
    #    cons.append("For FINREV_FED_17 with NDECoreExcel_Math_Grade8, compute metrics at state+year granularity: aggregate revenue by state_code and yr_data, join with NDECoreExcel_Math_Grade8 state and year; do not select district-level columns unless scores exist at the same granularity.")
    #if ("resultsdata15" in s_lower) and ("lod" in s_lower or "limit of detection" in n_lower):
    #    cons.append("For 'easiest to be tested' tasks, use the pesticide with lowest average LOD; if LOD is unavailable, use the highest count of test records.")
    meta = "\n".join([f"/* {c} */" for c in cons])
    return meta

cq_prefix_v1 = '''/* some examples are provided */
/* example question: */
Which artist/group is most productive?
/* example previous clarification questions and user replies: */
clarification questions: How to rank artist/group productivity? a) rank by the number of records produced, b) rank by the total number of downloads, c) other (please specify).
user: b) rank by the total number of downloads```
/* example reasoning and remaining ambiguity type*/
It is clear that the SQL answer should use ORDER BY and LIMIT 1 based on the sum of total downloads. However, it is unclear what columns should be used to represent the 'artist/group'.  Both the `artist` and the `groupName` columns contain information about 'artist/group'. ’‘AmbTableColumn’ remains.
/* example clarification question */
mul_choice_cq = "Which columns represent the 'artist/group' information? a) the artist column only, b) the groupName column only, c) both the artist column and the groupName column, d) other (please specify).”```

/* example question: */
Which Premier League matches ended in a draw in 2016?
/* example previous clarification questions and user replies: */
clarification questions: Is the year '2016' referring to? a) season is 2016, b) season is either 2015/2016 or 2016/2017, c) the date time is at year 2016, d) other (specify).
user: a) season is 2016,
clarification questions: How to find the 'Premier league'? a) consider all leagues, b) consider only the league with name 'Premier League', c) other (specify).
user: b) consider only the league with name 'Premier League'
/* example reasoning and remaining ambiguity type*/
It is clear that the SQL answer to this question needs to contain a WHERE clause for three conditions: 'Premier League', 'draw', and 'in 2016'. However, the question did not specify what fields should be contained in the output table. 'AmbOutput' remains.
/* example clarification question */
mul_choice_cq = “What fields represent the target 'matches'? a) all fields from football data table, b) the `league` column, c) other (specify).”
'''

feedback_v2 = """/* Given the following Natural Language Question: */
{nlq}
/* And the following Gold Query: */
{query}
/* Answer the following multiple choice clarification question truthfully based on the Gold Query: */
{question}

/* Follow these steps:
1. Identify which portion of the Gold Query answers the clarification question.
2. Evaluate the correctness of each multiple choice answer based only on the Gold Query.
3. If none of the choices are correct or you select "other (please specify)", provide a short answer for the clarification question.
4. Output the final answer in the format: answer_to_cq = "".

Let's proceed step by step. */
/* Only use information from the Gold Query; do not guess.
   Prefer answers that maintain consistent granularity and valid join semantics. */
"""

feedback_prefix_v1='''/* some examples are provided */
/* example question: */
How many acres burned in fires in California each year between 2000 and 2005?
/* example gold sql query*/
SELECT
  SUM(FIRE_SIZE),
  FIRE_YEAR
FROM Fires
WHERE
  State = "CA" AND FIRE_YEAR BETWEEN 2000 AND 2005
GROUP BY
  FIRE_YEAR
/* example clarification question*/
What information should the output table contain? a) two columns: the total acres burned and the year, b) one column: the total acres burned for each year, c) one column: the total acres burned across all target years, d) other (please specify).
/* example reasoning */
Output table is determined by the SELECT clause in the gold sql query. The gold query uses ‘SELECT  SUM(FIRE_SIZE), FIRE_YEAR’. As a result, the output table has two columns, the total acres burned and the year. Hence, choice a is correct.
/* example  answer*/
answer_to_cq = "a) two columns: the total acres burned and the year"

/* example question: */
What was the most common cause of fire between 2000 and 2005?
/* example gold sql query*/
SELECT
  STAT_CAUSE_DESCR
FROM Fires
WHERE
  FIRE_YEAR BETWEEN 2000 AND 2005
GROUP BY
  STAT_CAUSE_DESCR
ORDER BY
  COUNT(*) DESC
LIMIT 1;
/* example clarification question*/
Which information should be used to represent the 'cause of fire'? a) the code that represents the cause, b) the description of the cause, c) both the code and the description of the cause, d) other (please specify).
/* example reasoning */
The clarification question is asking for which column should be used to represent the cause of fire. The gold query uses the STAT_CAUSE_DESCR to represent the cause. As a result, choice b is correct.
/* example  answer*/
answer_to_cq = "b) the description of the cause"

/* example question: */
Whose CDs sells best?
/* example gold sql query*/
SELECT
  artist
FROM torrents
GROUP BY
  artist
ORDER BY
  SUM(totalSnatched) DESC
LIMIT 1;
/* example clarification question*/
Which column should be used to identify music related to 'CD'? a) groupName, b) tag, c) releaseType, d) other (please specify)
/* example reasoning */
The gold query does not use a WHERE clause to filter the CDs. Hence, the CD information is not contained in the tag column or the release type column. As a result, choice a, b, and c are all wrong.
/* example  answer*/
answer_to_cq = “d) Consider all music; No filter on ‘CD’ ”

/* example question: */
How many people wrote comments for the question "Any additional notes or comments."? */
/* example gold sql query*/
SELECT COUNT(T1.UserID) FROM Answer AS T1 INNER JOIN Question AS T2 ON T1.QuestionID = T2.questionid WHERE T2.questiontext LIKE 'Any additional notes or comments' AND T1.AnswerText IS NOT NULL
/* example clarification question*/
How to determine if a user has provided comments? a) no check needed, b) see if `AnswerText` column has empty string, c) other (please specify).
/* example reasoning */
In the gold SQL query, it checks “T1.AnswerText IS NOT NULL”. Hence, choice a and b are both wrong.
/* example  answer*/
answer_to_cq = "c) ‘wrote comments’ imply `AnswerText` is not a NULL value".

/* example question: */
Calculate the difference between the number of customers and the number of subscribers who did the trip in June 2013. 
/* example gold sql query*/
SELECT SUM(IIF(subscription_type = 'Subscriber', 1, 0)) - SUM(IIF(subscription_type = 'Customer', 1, 0)) FROM trip WHERE start_date LIKE '6/%/2013%'
/* example clarification question*/
What predicate value should be used to determine a trip in June 2013? a) start_data > 06/2013, b) start_data = ‘June 2013’, c) other (please specify).
/* example reasoning */
The gold sql query uses start_date LIKE '6/%/2013%' to find trips in June 2013.
/* example  answer*/
answer_to_cq = "c) start_date LIKE '6/%/2013%'"


/* example question: */
Identify the players who weigh 120 kg.
/* example gold sql query*/
SELECT T2.PlayerName FROM weight_info AS T1 INNER JOIN PlayerInfo AS T2 ON T1.weight_id = T2.weight WHERE T1.weight_in_kg = 120
/* example clarification question*/
What fields should be contained in the output? a) one column of player name, b) one column of player id, c) two columns of player name and player ids, d) other (please specify).
/* example reasoning */
The gold query selects ‘SELECT T2.PlayerName’. Hence, a is correct.
/* example  answer*/
answer_to_cq = "a) one column of player name"

/* example question: */
How many reviews are created for the podcast "Scaling Global" under?
/* example gold sql query*/
SELECT COUNT(T2.content) FROM podcasts AS T1 INNER JOIN reviews AS T2 ON T2.podcast_id = T1.podcast_id WHERE T1.title = 'Scaling Global'
/* example clarification question*/
Which column represents the reviews? a) `podcast` column, b) `content` column, c) other (please specify).
/* example reasoning */
The gold query uses “COUNT(T2.content)” to determine the number of reviews. Hence, b is correct in which the `content` column represents the reviews.
/* example  answer*/
answer_to_cq = "b) `content` column"
'''

selfdebug_examples_prefix = '''/* Given the following incorrect sql asnwers: */
SELECT creation, COUNT(*) FROM department GROUP BY creation ORDER BY
COUNT(*) DESC LIMIT 1
/* Answer the following with no explanation: In which year were most departments established? */
SELECT creation FROM department GROUP BY creation ORDER BY COUNT(*) DESC LIMIT 1
-------
/* Given the following incorrect sql asnwers: */
SELECT customers.customer_name FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.order_status = "On Road" AND orders.order_status = "Shipped"
/* Answer the following with no explanation: Which customers have both "On Road" and "Shipped" as order status? List the customer names. */
SELECT customers.customer_name FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.order_status = "On Road" INTERSECT SELECT customers.customer_name FROM customers JOIN orders ON customers.customer_id = orders.customer_id WHERE orders.order_status = "Shipped"
-------
/* Given the following incorrect sql asnwers: */
SELECT COUNT(status) FROM city
/* How many different statuses do cities have? */
SELECT COUNT(DISTINCT status) FROM city
-------'''

def make_selfdebug_few_shot():
    examples = selfdebug_examples_prefix.split('-------')
    res = []
    for i in range(1, 4):
        prefix = []
        for j in range(i):
            prefix.append(examples[j])
        res.append('\n'.join(prefix))
    return res

fewshot_prefix = "/* some examples are provided */\n"

