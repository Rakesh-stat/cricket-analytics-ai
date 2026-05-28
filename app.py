import os
import re
import duckdb
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
st.set_page_config(page_title="Cricket Analytics Assistant", page_icon="🏏")

st.title("🏏 Cricket Analytics Assistant")
st.write("Ask cricket stats questions from your ball-by-ball database.")
@st.cache_resource
def get_connection():
    return duckdb.connect("cricket.db")

con = get_connection()

SCHEMA = """
matches(match_id, date, event, season, match_type, venue, city, team1, team2, winner,win_by_runs,win_by_wickets,
toss_winner, toss_decision, match_number, stage)

deliveries(match_id, innings, batting_team, over, ball, batter, bowler,
non_striker, runs_batter, runs_extras, runs_total, extras_type,
is_wicket, player_out, wicket_kind)
"""

def clean_sql(text):
    text = text.strip()
    text = re.sub(r"```sql", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)
    return text.strip()

def generate_sql(question):
    prompt = f"""
You are a cricket analytics SQL assistant.

Use DuckDB SQL only.

Schema:
{SCHEMA}

Rules:
Generate only SQL.
- Do not use markdown.
- Do not explain.
- Only SELECT queries.
- IPL refers to Indian Premier League.
- When the user says IPL, use:
  LOWER(m.event) LIKE '%indian premier league%'
Do not use outside cricket knowledge.
- If the result is empty, say the database does not contain enough data.
- Do not invent names, runs, or wickets.
- Keep it concise.
- Limit results to 10 unless user asks otherwise. 
-Strike rate =(SUM(runs_batter) * 100.0) / COUNT(*)
- Economy rate =SUM(runs_total) * 6.0 / COUNT(*) 
- Batting average =SUM(runs_batter) / number_of_times_out
player_out is the batter who got out.
- bowler is the bowler who delivered the ball.
- For "who took most wickets", group by bowler, NOT player_out.
- Do NOT group by player_out for bowling wicket questions and also wicket_kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
- If the question asks for multiple statistics or awards,
generate SQL that returns all requested information.
- Orange Cap = individual batter with most total runs in an IPL season.
- Purple Cap = highest wicket taker in IPL season.
Cricket team result rules:
- winner is the team that won the match.
- For most losses, count the opposite team of winner.
-Do NOT filter is_wicket = true when counting matches played.
-Boundary percentage typically refers to the proportion of runs scored through boundaries (fours and sixes) compared to the total runs scored. 
-Cups/titles/championships won = number of IPL final matches won.
- IPL cups/titles are won only by winning the final match.
- Do not count all match wins as cups.
- Use stage = 'Final' or match_number = 'Final' to identify finals.
- Bowling average =total runs conceded / wickets taken
- Wickets for bowling average exclude:
  run out,
  retired hurt,
  retired out,
  obstructing the field
- Lower bowling average is better.
- Use runs_total for runs conceded.
- For total matches played by teams:
  combine appearances as both team1 and team2 using UNION ALL,
  then SUM the counts grouped by team.
Question:
{question}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return clean_sql(response.choices[0].message.content)

def explain_answer(question, result):
    prompt = f"""
User question:
{question}

Result:
{result.to_string(index=False)}

Give a clear natural-language cricket analytics answer.
Do not mention SQL.
Keep it concise.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return response.choices[0].message.content.strip()


question = st.text_input("Ask a question", placeholder="Who is the top run scorer in IPL 2015?")


if st.button("Ask") and question:
    try:
        sql = generate_sql(question)

        if not sql.lower().startswith("select"):
            st.error("Generated query was not a SELECT query.")
            st.code(sql)
        else:
            result = con.execute(sql).fetchdf()

            answer = explain_answer(question, result)

            st.subheader("Answer")
            st.write(answer)

            st.dataframe(result)
            st.subheader("Data")
            

            if not result.empty and len(result.columns) >= 2:
                label_col = result.columns[0]
                value_col = result.columns[1]

            if result[value_col].dtype in ["int64", "float64", "int32", "float32"]:
                chart_data = result[[label_col, value_col]].set_index(label_col)
                st.subheader("Chart")
                st.bar_chart(chart_data)

            

            with st.expander("Generated SQL"):
                st.code(sql, language="sql")

    except Exception as e:
        st.error(str(e))

st.markdown("""
### Example Questions
- Who scored most runs in IPL 2016?
- Which bowler took most wickets in IPL history?
- Who faced most dot balls?
- Which team won most IPL matches?
""")