import re


TEAM_ALIASES = {
    "csk": "Chennai Super Kings",
    "mi": "Mumbai Indians",
    "rcb": "Royal Challengers Bangalore",
    "kkr": "Kolkata Knight Riders",
    "srh": "Sunrisers Hyderabad",
    "dc": "Delhi Capitals",
    "dd": "Delhi Daredevils",
    "rr": "Rajasthan Royals",
    "kxip": "Kings XI Punjab",
    "pbks": "Punjab Kings",
    "gt": "Gujarat Titans",
    "lsg": "Lucknow Super Giants",
}


def extract_year_filter(q):
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", q)]

    if not years:
        return None

    years = sorted(set(years))

    if len(years) == 1:
        return f"EXTRACT(YEAR FROM CAST(m.date AS DATE)) = {years[0]}"

    # Handles:
    # from 2018 to 2020
    # between 2018 and 2020
    # 2018-2020
    # 2018 to 2020
    if (
        "from" in q
        or "between" in q
        or "to" in q
        or "-" in q
    ):
        return f"EXTRACT(YEAR FROM CAST(m.date AS DATE)) BETWEEN {years[0]} AND {years[-1]}"

    # Handles:
    # 2018, 2019
    # 2018 and 2019
    # 2018 2019
    year_list = ", ".join(str(y) for y in years)
    return f"EXTRACT(YEAR FROM CAST(m.date AS DATE)) IN ({year_list})"


def extract_stage_filter(q):
    if "final" in q:
        return """
        (
            LOWER(CAST(m.stage AS VARCHAR)) = 'final'
            OR LOWER(CAST(m.match_number AS VARCHAR)) = 'final'
        )
        """

    if "playoff" in q or "playoffs" in q:
        return """
        (
            LOWER(CAST(m.stage AS VARCHAR)) LIKE '%qualifier%'
            OR LOWER(CAST(m.stage AS VARCHAR)) LIKE '%eliminator%'
            OR LOWER(CAST(m.stage AS VARCHAR)) = 'final'
            OR LOWER(CAST(m.match_number AS VARCHAR)) LIKE '%qualifier%'
            OR LOWER(CAST(m.match_number AS VARCHAR)) LIKE '%eliminator%'
            OR LOWER(CAST(m.match_number AS VARCHAR)) = 'final'
        )
        """

    return None


def extract_team_filter(q):
    for alias, team_name in TEAM_ALIASES.items():
        if re.search(rf"\b{alias}\b", q):
            return f"(m.team1 = '{team_name}' OR m.team2 = '{team_name}' OR d.batting_team = '{team_name}')"

    return None


def build_filters(q):
    filters = ["LOWER(m.event) LIKE '%indian premier league%'"]

    year_filter = extract_year_filter(q)
    stage_filter = extract_stage_filter(q)
    team_filter = extract_team_filter(q)

    if year_filter:
        filters.append(year_filter)

    if stage_filter:
        filters.append(stage_filter)

    if team_filter:
        filters.append(team_filter)

    return "\n      AND ".join(filters)


def get_template_sql(question):
    q = question.lower()
    filters = build_filters(q)

    if "orange cap" in q:
        return f"""
WITH batter_runs AS (
    SELECT
        EXTRACT(YEAR FROM CAST(m.date AS DATE)) AS season,
        d.batter,
        SUM(d.runs_batter) AS total_runs
    FROM deliveries d
    JOIN matches m ON d.match_id = m.match_id
    WHERE {filters}
    GROUP BY EXTRACT(YEAR FROM CAST(m.date AS DATE)), d.batter
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY season
               ORDER BY total_runs DESC
           ) AS rn
    FROM batter_runs
)
SELECT season,
       batter AS orange_cap_winner,
       total_runs
FROM ranked
WHERE rn = 1
ORDER BY season;
"""
    if "purple cap" in q:
        return f"""
WITH bowler_wickets AS (
    SELECT
        EXTRACT(YEAR FROM CAST(m.date AS DATE)) AS season,
        d.bowler,
        COUNT(*) AS wickets
    FROM deliveries d
    JOIN matches m ON d.match_id = m.match_id
    WHERE {filters}
      AND d.is_wicket = true
      AND d.wicket_kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
     GROUP BY EXTRACT(YEAR FROM CAST(m.date AS DATE)), d.bowler
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY season
               ORDER BY wickets DESC
           ) AS rn
    FROM bowler_wickets
)
SELECT season,
       bowler AS purple_cap_winner,
       wickets
FROM ranked
WHERE rn = 1
ORDER BY season;
"""

    if "centuries" in q or "100s" in q:
        return f"""
WITH innings_runs AS (
    SELECT
        d.match_id,
        d.innings,
        d.batter,
        SUM(d.runs_batter) AS runs
    FROM deliveries d
    JOIN matches m ON d.match_id = m.match_id
    WHERE {filters}
    GROUP BY d.match_id, d.innings, d.batter
)
SELECT batter,
       COUNT(*) AS centuries
FROM innings_runs
WHERE runs >= 100
GROUP BY batter
ORDER BY centuries DESC
LIMIT 10;
"""

    if "fifties" in q or "50s" in q or "half centuries" in q:
        return f"""
WITH innings_runs AS (
    SELECT
        d.match_id,
        d.innings,
        d.batter,
        SUM(d.runs_batter) AS runs
    FROM deliveries d
    JOIN matches m ON d.match_id = m.match_id
    WHERE {filters}
    GROUP BY d.match_id, d.innings, d.batter
)
SELECT batter,
       COUNT(*) AS fifties
FROM innings_runs
WHERE runs BETWEEN 50 AND 99
GROUP BY batter
ORDER BY fifties DESC
LIMIT 10;
"""

    if "fastest century" in q:
        return f"""
WITH legal_balls AS (
    SELECT
        d.match_id,
        d.innings,
        d.batter,
        d.over,
        d.ball,
        d.runs_batter,
        CASE
            WHEN d.extras_type = 'wides' THEN 0
            ELSE 1
        END AS legal_ball
    FROM deliveries d
    JOIN matches m ON d.match_id = m.match_id
    WHERE {filters}
),
running AS (
    SELECT *,
           SUM(runs_batter) OVER (
               PARTITION BY match_id, innings, batter
               ORDER BY over, ball
           ) AS cumulative_runs,
           SUM(legal_ball) OVER (
               PARTITION BY match_id, innings, batter
               ORDER BY over, ball
           ) AS balls_faced
    FROM legal_balls
),
century_ball AS (
    SELECT
        match_id,
        innings,
        batter,
        MIN(balls_faced) AS balls_to_100
    FROM running
    WHERE cumulative_runs >= 100
    GROUP BY match_id, innings, batter
)
SELECT batter,
       balls_to_100,
       match_id,
       innings
FROM century_ball
ORDER BY balls_to_100 ASC
LIMIT 10;
"""

    if "dot ball" in q or "dot balls" in q:
        return f"""
SELECT d.batter,
       COUNT(*) AS dot_balls
FROM deliveries d
JOIN matches m ON d.match_id = m.match_id
WHERE {filters}
  AND d.runs_total = 0
GROUP BY d.batter
ORDER BY dot_balls DESC
LIMIT 10;
"""

    if "six" in q or "sixes" in q:
        return f"""
SELECT d.batter,
       COUNT(*) AS sixes
FROM deliveries d
JOIN matches m ON d.match_id = m.match_id
WHERE {filters}
  AND d.runs_batter = 6
GROUP BY d.batter
ORDER BY sixes DESC
LIMIT 10;
"""

    if "four" in q or "fours" in q:
        return f"""
SELECT d.batter,
       COUNT(*) AS fours
FROM deliveries d
JOIN matches m ON d.match_id = m.match_id
WHERE {filters}
  AND d.runs_batter = 4
GROUP BY d.batter
ORDER BY fours DESC
LIMIT 10;
"""

    if "bowling average" in q:
        return f"""
SELECT d.bowler,
       SUM(d.runs_total) AS runs_conceded,
       COUNT(*) FILTER (
           WHERE d.is_wicket = true
           AND d.wicket_kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
       ) AS wickets,
       SUM(d.runs_total) * 1.0 /
       NULLIF(
           COUNT(*) FILTER (
               WHERE d.is_wicket = true
               AND d.wicket_kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
           ),
           0
       ) AS bowling_average
FROM deliveries d
JOIN matches m ON d.match_id = m.match_id
WHERE {filters}
GROUP BY d.bowler
HAVING wickets > 0
ORDER BY bowling_average ASC
LIMIT 10;
"""

    return None