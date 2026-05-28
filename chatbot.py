import os
import duckdb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
con = duckdb.connect("cricket.db")

SCHEMA = """
Tables:

matches(
    match_id, date, event, season, match_type, venue, city, team1, team2, winner,
    toss_winner, toss_decision, match_number,season, player_of_match, stage)

deliveries(
  match_id, innings, batting_team, over, ball, batter, bowler,
  non_striker, runs_batter, runs_extras, runs_total,
  extras_type, is_wicket, player_out, wicket_kind
)
"""

def generate_sql(question):
    prompt = f"""
You are a cricket analytics SQL assistant.

Use DuckDB SQL only.

Database schema:
{SCHEMA}

Rules:
- Generate only SQL.
- Do not use markdown.
- Do not explain.
- Only SELECT queries.
- Limit results to 10 unless user asks otherwise.

Question:
{question}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()


def answer_question(question):
    sql = generate_sql(question)

    print("\nGenerated SQL:")
    print(sql)

    result = con.execute(sql).fetchdf()

    explain_prompt = f"""
User question:
{question}

SQL result:
{result.to_string(index=False)}

Give a clear cricket analytics answer in simple language.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": explain_prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    question = input("Ask cricket question: ")
    answer = answer_question(question)
    print("\nAnswer:")
    print(answer)