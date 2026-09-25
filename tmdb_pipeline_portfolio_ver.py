# Team 3: The Movie Magic Team!
# (Amelia, Riani, Fauzi, Clarence)
# Version 1.23 (Objective Documentation & Visualizations)

# ---------------------------------------------------------
# IMPORTING REQUIRED LIBRARIES
# ---------------------------------------------------------

# Provides operating system interfaces (e.g., creating folders)
import os

# Used to insert deliberate pauses so we don't exceed TMDB's rate limits
import time

# Handles HTTP requests to the TMDB API, acting like a browser in Python
import requests

# Powerful data manipulation library; here we use it to display SQL results as clean tables
import pandas as pd

# Converts string dates from TMDB into Python date objects for PostgreSQL
from datetime import datetime

# --- VISUALIZATION LIBRARIES ---

# Core plotting library; provides the canvas and rendering for all charts
import matplotlib.pyplot as plt

# High‑level interface for attractive statistical graphics; builds on matplotlib
import seaborn as sns

# --- DATABASE LIBRARIES (SQLAlchemy) ---

# SQLAlchemy core: creates database engines, defines table columns and data types
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, BigInteger, Boolean, ForeignKey

# Declarative base allows us to define database tables as Python classes
# sessionmaker creates session objects that act as transaction workspaces
from sqlalchemy.orm import declarative_base, sessionmaker

# The 'text' function lets us write raw SQL queries that are passed directly to PostgreSQL
from sqlalchemy.sql import text


# ==========================================
# 1. CONFIGURATION & DATABASE SETUP
# ==========================================

# Your personal TMDB API key – required to authenticate every request
TMDB_API_KEY = # API Key is taken from own account and cannot be shown here

# Connection string for PostgreSQL: tells SQLAlchemy where the database lives,
# which user to log in as, and which database to open
# Password cannot be revealed here
DB_URI = "postgresql://postgres:{password}@localhost:5432/tmdb_project"

# Create the database engine – this manages the connection pool and
# translates Python operations into SQL statements behind the scenes
engine = create_engine(DB_URI)

# Factory class for all ORM‑mapped tables; every table class inherits from it
Base = declarative_base()

# Session factory: each Session object is a temporary workspace where we
# add, modify, or delete records before finally committing them to the database
Session = sessionmaker(bind=engine)


# ==========================================
# 2. DEFINING THE DATABASE SCHEMA (ORM)
# ==========================================

# ----- genres table: stores all possible movie categories (Action, Comedy, etc.) -----
class Genre(Base):
    __tablename__ = 'genres'

    # Unique numeric ID from TMDB – used as primary key
    id = Column(Integer, primary_key=True)

    # Human‑readable genre name, e.g., "Science Fiction"
    name = Column(String)

# ----- movies table: stores the core film data for each movie -----
class Movie(Base):
    __tablename__ = 'movies'

    # TMDB's unique movie identifier – primary key
    id = Column(Integer, primary_key=True)

    # The movie's official title
    title = Column(String)

    # Release date as a proper Date type (not a string)
    release_date = Column(Date)

    # Worldwide revenue and production budget – BigInteger handles large numbers
    # that exceed the standard 32‑bit integer limit (2.1 billion)
    revenue = Column(BigInteger)
    budget = Column(BigInteger)

    # Average audience rating (e.g., 8.5) and total number of votes
    vote_average = Column(Float)
    vote_count = Column(Integer)

    # Original production countries stored as a string representation of a list
    origin_countries = Column(String)

    # Additional columns added specifically to answer the team's research questions
    runtime = Column(Integer)          # Movie length in minutes
    is_franchise = Column(Boolean)     # True if movie belongs to a collection (franchise)

# ----- bridge table (many‑to‑many) linking movies to genres -----
class MovieGenre(Base):
    __tablename__ = 'movie_genres'

    # Surrogate primary key; auto‑increments for each bridge record
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys pointing back to movies.id and genres.id
    movie_id = Column(Integer, ForeignKey('movies.id'))
    genre_id = Column(Integer, ForeignKey('genres.id'))

# ----- DEVELOPMENT‑ONLY: drop all existing tables -----
# This line completely removes any previous versions of the tables defined above.
# It ensures that schema changes (e.g., new columns) are applied cleanly on every run.
# In production, you would comment this out to avoid accidental data loss.
# *** PLEASE DO NOT DELETE THIS NEXT LINE -_-" -Clarence
Base.metadata.drop_all(engine)

# Re‑create all tables with the current schema – if they already exist, they are rebuilt
Base.metadata.create_all(engine)


# ==========================================
# 3. ETL PIPELINE (Extract, Transform, Load)
# ==========================================

def run_etl_pipeline():
    """
    Main ETL routine: fetches genres and movies from TMDB, transforms the data,
    and loads it into the PostgreSQL tables.
    """
    # Open a new database session (workspace) for all operations in this function
    session = Session()
    print("Starting ETL Pipeline...")

    # --- STEP 1: EXTRACTING GENRES ---
    print("Fetching Genres...")

    # Build the URL to request the official list of movie genres from TMDB
    genres_url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}&language=en-US"

    # Send the GET request and parse the JSON response into a Python dictionary
    genres_resp = requests.get(genres_url).json()

    # Loop through each genre object returned by the API
    for g in genres_resp.get('genres', []):
        # Check if this genre ID already exists in our database – if not, we add it
        if not session.query(Genre).filter_by(id=g['id']).first():
            # Instantiate a new Genre object and stage it for insertion
            new_genre = Genre(id=g['id'], name=g['name'])
            session.add(new_genre)

    # Commit all newly added genres to the database in one batch
    session.commit()

    # --- STEP 2: EXTRACTING MOVIES ---
    print("Fetching Movies (Singapore Releases)...")

    # Iterate over the first 3 pages of discovery results (we want a decent sample)
    for page in range(1, 4):
        # Construct the discovery URL with region set to SG (Singapore) and sorted by revenue descending
        discover_url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&region=SG&sort_by=revenue.desc&page={page}"

        # Send the request and parse the JSON; this returns a list of movie summaries
        discover_resp = requests.get(discover_url).json()

        # Extract the list of basic movie objects from the response; default to empty list if missing
        movies_list = discover_resp.get('results', [])

        # For each summary, we perform a "deep fetch" to get detailed data (revenue, budget, runtime)
        for basic_movie in movies_list:
            movie_id = basic_movie['id']   # TMDB's unique ID for this movie

            # If this movie already exists in our database, skip to avoid duplicates
            if session.query(Movie).filter_by(id=movie_id).first():
                continue

            # Pause 0.25 seconds between requests to stay well below TMDB's rate limit
            # (approx 4 requests per second maximum)
            time.sleep(0.25)

            # Build the detailed movie endpoint URL
            detail_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}"

            # Send the request for full details
            detail_resp = requests.get(detail_url)

            # Only process if the request succeeded (HTTP status 200 OK)
            if detail_resp.status_code == 200:
                # Parse the JSON response into a dictionary
                m_data = detail_resp.json()

                # Determine if the movie belongs to a franchise (i.e., has a collection)
                # True if 'belongs_to_collection' exists and is not None
                is_franchise = True if m_data.get('belongs_to_collection') else False

                # Extract the release date string (format: YYYY-MM-DD)
                release_date_str = m_data.get('release_date')
                # Convert it to a Python date object; if missing, set to None
                release_date = datetime.strptime(release_date_str, '%Y-%m-%d').date() if release_date_str else None

                # Build a new Movie object with all fields, using .get() to supply defaults for missing data
                new_movie = Movie(
                    id=m_data.get('id'),
                    title=m_data.get('title'),
                    release_date=release_date,
                    revenue=m_data.get('revenue', 0),
                    budget=m_data.get('budget', 0),
                    vote_average=m_data.get('vote_average', 0.0),
                    vote_count=m_data.get('vote_count', 0),
                    # Convert the list of countries to a string (so we can store it in a single column)
                    origin_countries=str(m_data.get('origin_country', [])),
                    runtime=m_data.get('runtime', 0),
                    is_franchise=is_franchise
                )
                # Stage the new movie record for insertion
                session.add(new_movie)

                # Now iterate over the genres attached to this movie
                for genre in m_data.get('genres', []):
                    # Create a bridge record that links this movie to its genre
                    movie_genre = MovieGenre(movie_id=movie_id, genre_id=genre['id'])
                    session.add(movie_genre)

    # Commit all staged movies and bridge records to the database in a single transaction
    session.commit()
    # Close the session to free up memory and database connections
    session.close()
    print("ETL Pipeline Completed!\n")


# ==========================================
# 4. VISUAL SETTINGS & FORMATTING HELPERS
# ==========================================
# This section was contributed to give the charts a consistent, presentation‑ready look.
# It centralises styling, adds a source note, and provides currency‑formatting helpers.

def setup_chart_style():
    """
    Applies a clean, consistent style to all matplotlib/seaborn charts.
    We use a white background, remove unnecessary spines, and set readable font sizes.
    """
    # Use Seaborn's "white" theme (no gridlines by default) with notebook‑sized fonts
    sns.set_theme(style="white", context="notebook")

    # Override matplotlib's default parameters for all subsequent figures
    plt.rcParams.update({
        "figure.dpi": 120,                # Screen resolution while running
        "savefig.dpi": 200,               # Higher DPI for saved PNGs
        "font.family": "DejaVu Sans",     # Clean, widely‑available sans‑serif font
        "axes.titleweight": "bold",       # Make chart titles bold
        "axes.titlesize": 18,             # Title font size
        "axes.labelsize": 11,             # Axis label font size
        "xtick.labelsize": 10,            # X‑axis tick labels size
        "ytick.labelsize": 10,            # Y‑axis tick labels size
        "axes.spines.top": False,         # Remove the top border line
        "axes.spines.right": False,       # Remove the right border line
        "axes.spines.left": False,        # Remove the left border line
        "axes.spines.bottom": False,      # Remove the bottom border line
    })

def add_source_note():
    """
    Adds a small, light‑grey attribution note in the bottom‑left corner of the current figure.
    The note reads "Source: TMDb | TMMT" (TMMT = Team 3 Movie Magic Team).
    """
    plt.figtext(
        0.01, 0.01,                     # Position: 1% from left, 1% from bottom (figure‑relative)
        "Source: TMDb | TMMT",          # Note text
        ha="left",                      # Left‑align the text at the anchor
        fontsize=8,                     # Small and unobtrusive
        color="#777777"                 # Light grey so it doesn't distract
    )

def format_billions(value, _position=None):
    """
    Formats a number as a currency string in billions, e.g., 1,500,000,000 → "$1.5B".
    The '_position' parameter is accepted but unused so the function can be used
    as a matplotlib tick formatter if needed.
    """
    return f"${value / 1_000_000_000:.1f}B"

def format_millions(value, _position=None):
    """
    Formats a number as a currency string in millions, e.g., 25,000,000 → "$25M".
    Useful for smaller values that would otherwise be shown as 0.0B.
    """
    return f"${value / 1_000_000:.0f}M"


# ==========================================
# 5. DATA ANALYSIS & VISUALIZATIONS
# ==========================================

def run_analysis():
    """
    Executes five analytical SQL queries, prints the results to the terminal,
    and generates corresponding charts saved in the 'visualizations' folder.
    """
    # Print a clear banner so the user knows the analysis phase has started
    print("=" * 60)
    print("TEAM 3 MOVIE MAGIC's RESEARCH FINDINGS")
    print("=" * 60)

    # Create the output folder 'visualizations' if it doesn't already exist
    os.makedirs("visualizations", exist_ok=True)

    # Apply the unified chart styling defined above
    setup_chart_style()

    # -----------------------------------------------------
    # Q1: RELEASE MONTH
    # Which release month brings in the highest average revenue?
    # -----------------------------------------------------

    print("\n1. Which release month brings in the highest average revenue?")

    # SQL: extract calendar month, calculate average revenue and movie count.
    # We exclude movies with revenue ≤ 10000 (likely placeholder values) and
    # those with NULL release_date to avoid errors in EXTRACT.
    query_1 = text("""
        SELECT
            EXTRACT(MONTH FROM release_date) AS release_month,
            CAST(AVG(revenue) AS BIGINT) AS avg_revenue,
            COUNT(*) AS movie_count
        FROM movies
        WHERE revenue > 10000
          AND release_date IS NOT NULL
        GROUP BY release_month
        ORDER BY release_month;
    """)

    # Execute the query and load the result set into a pandas DataFrame
    df1 = pd.read_sql(query_1, engine)

    # Dictionary to map month numbers (1‑12) to short English month names
    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }

    # EXTRACT returns a float in PostgreSQL; convert to int so we can use it as a dict key
    df1["release_month"] = df1["release_month"].astype(int)
    # Add a new column with the human‑readable month name
    df1["month_name"] = df1["release_month"].map(month_names)

    # Print the raw table to the terminal without the pandas index
    print(df1.to_string(index=False))

    # --- PLOT 1: Vertical bar chart of average revenue by month ---
    fig, ax = plt.subplots(figsize=(11, 6))

    # Draw the bars; convert revenue to billions for easier axis scaling
    bars = ax.bar(
        df1["month_name"],
        df1["avg_revenue"] / 1_000_000_000,
        color="#D9D9D9",        # Default light grey
        edgecolor="none"
    )

    # Identify the month with the highest average revenue
    max_idx = df1["avg_revenue"].idxmax()

    # Loop through all bars and colour the winning month red
    for i, bar in enumerate(bars):
        if df1.index[i] == max_idx:
            bar.set_color("#C62828")   # Deep red

    # Chart title: bold, left‑aligned, all‑caps headline style
    ax.set_title(
        "WHEN DO MOVIES MAKE THE MOST MONEY?",
        loc="left",
        pad=20
    )

    # Y‑axis label (what the bar height represents), X‑axis label is empty because months are self‑explanatory
    ax.set_ylabel("Average worldwide revenue (USD billions)")
    ax.set_xlabel("")

    # Add faint horizontal gridlines to help estimate values
    ax.grid(axis="y", alpha=0.15)
    # Ensure gridlines are drawn behind the bars
    ax.set_axisbelow(True)

    # Annotate each bar with its exact value in billions
    for bar, value in zip(
        bars,
        df1["avg_revenue"] / 1_000_000_000
    ):
        ax.text(
            bar.get_x() + bar.get_width() / 2,  # Horizontal centre of the bar
            bar.get_height(),                   # Just above the top of the bar
            f"${value:.1f}B",
            ha="center",
            va="bottom",
            fontsize=9
        )

    # Stamp the data source note
    add_source_note()

    # Adjust layout, leaving extra bottom margin so the source note is not cut off
    plt.tight_layout(rect=[0, 0.03, 1, 1])

    # Save the chart as a high‑resolution PNG
    plt.savefig(
        "visualizations/Q1_Revenue_By_Month.png",
        bbox_inches="tight"
    )

    # Close the figure to free memory and prevent it from interfering with the next plot
    plt.close()

    # -----------------------------------------------------
    # Q2: FRANCHISE VS ORIGINAL
    # Do franchises earn more than original standalone movies?
    # -----------------------------------------------------

    print("\n2. Do franchises earn more than original standalone movies?")

    # SQL: use CASE to convert boolean is_franchise into readable labels,
    # then average revenue and count for each group.
    query_2 = text("""
        SELECT
            CASE
                WHEN is_franchise = TRUE
                    THEN 'Franchise'
                ELSE 'Original'
            END AS movie_type,
            CAST(AVG(revenue) AS BIGINT) AS avg_revenue,
            COUNT(*) AS movie_count
        FROM movies
        WHERE revenue > 10000
        GROUP BY is_franchise
        ORDER BY avg_revenue DESC;
    """)

    df2 = pd.read_sql(query_2, engine)
    print(df2.to_string(index=False))

    # --- PLOT 2: Two‑bar comparison chart ---
    fig, ax = plt.subplots(figsize=(9, 6))

    # Draw the bars; colour the 'Franchise' bar red and the 'Original' bar light grey
    bars = ax.bar(
        df2["movie_type"],
        df2["avg_revenue"] / 1_000_000_000,
        color=["#C62828" if x == "Franchise" else "#D9D9D9"
               for x in df2["movie_type"]],
        width=0.55
    )

    ax.set_title(
        "DO FRANCHISES MAKE MORE MONEY?",
        loc="left",
        pad=20
    )

    ax.set_ylabel("Average worldwide revenue (USD billions)")
    ax.set_xlabel("")

    ax.grid(axis="y", alpha=0.15)
    ax.set_axisbelow(True)

    # Label each bar with its exact value, in bold for emphasis
    for bar, value in zip(
        bars,
        df2["avg_revenue"] / 1_000_000_000
    ):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"${value:.2f}B",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold"
        )

    add_source_note()
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(
        "visualizations/Q2_Franchise_vs_Original.png",
        bbox_inches="tight"
    )
    plt.close()

    # -----------------------------------------------------
    # Q3: RUNTIME TREND
    # Are movies getting longer?
    # -----------------------------------------------------

    print("\n3. Are movies getting longer?")

    # SQL: extract release year, compute average runtime (rounded to 1 decimal)
    # for each year, filtering out movies with runtime ≤ 0 (missing data).
    query_3 = text("""
        SELECT
            EXTRACT(YEAR FROM release_date)::INTEGER AS release_year,
            ROUND(AVG(runtime), 1) AS avg_runtime,
            COUNT(*) AS movie_count
        FROM movies
        WHERE runtime > 0
          AND release_date IS NOT NULL
        GROUP BY release_year
        ORDER BY release_year;
    """)

    df3 = pd.read_sql(query_3, engine)
    print(df3.to_string(index=False))

    # --- PLOT 3: Line chart to show trend over time ---
    fig, ax = plt.subplots(figsize=(11, 6))

    # Plot the line with markers at each data point
    ax.plot(
        df3["release_year"],
        df3["avg_runtime"],
        color="#C62828",
        linewidth=2.8,
        marker="o",
        markersize=5
    )

    ax.set_title(
        "ARE MOVIES GETTING LONGER?",
        loc="left",
        pad=20
    )

    ax.set_ylabel("Average runtime (minutes)")
    ax.set_xlabel("Release year")

    ax.grid(axis="y", alpha=0.15)
    ax.set_axisbelow(True)

    # If we have many years, only show a subset of x‑axis ticks to avoid overlap
    years = df3["release_year"].tolist()
    if len(years) > 12:
        # Choose roughly every 10th year as a tick
        tick_years = years[::max(1, len(years) // 10)]
        ax.set_xticks(tick_years)

    add_source_note()
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(
        "visualizations/Q3_Runtime_Trend.png",
        bbox_inches="tight"
    )
    plt.close()

    # -----------------------------------------------------
    # Q4: REVENUE BY GENRE
    # Which genres generate the highest average revenue?
    # -----------------------------------------------------

    print("\n4. Which genres generate the highest average revenue?")

    # SQL: join movies → movie_genres → genres to get genre names.
    # We require at least 2 distinct movies per genre (HAVING) so a single
    # blockbuster cannot skew the average for a niche genre.
    # LIMIT 8 keeps the chart focused on the top performers.
    query_4 = text("""
        SELECT
            g.name AS genre_name,
            CAST(AVG(m.revenue) AS BIGINT) AS avg_revenue,
            COUNT(DISTINCT m.id) AS movie_count
        FROM movies m
        JOIN movie_genres mg
            ON m.id = mg.movie_id
        JOIN genres g
            ON g.id = mg.genre_id
        WHERE m.revenue > 10000
        GROUP BY g.name
        HAVING COUNT(DISTINCT m.id) >= 2
        ORDER BY avg_revenue DESC
        LIMIT 8;
    """)

    df4 = pd.read_sql(query_4, engine)
    print(df4.to_string(index=False))

    # Sort in ascending order for plotting – horizontal bars draw from bottom up,
    # so this places the highest‑revenue genre at the top.
    df4 = df4.sort_values("avg_revenue", ascending=True)

    # --- PLOT 4: Horizontal bar chart ---
    fig, ax = plt.subplots(figsize=(11, 6.5))

    # barh() creates horizontal bars, which are easier to read with long genre names
    bars = ax.barh(
        df4["genre_name"],
        df4["avg_revenue"] / 1_000_000_000,
        color="#D9D9D9"
    )

    # The last bar (highest revenue) is highlighted in red
    bars[-1].set_color("#C62828")

    ax.set_title(
        "WHICH GENRES BRING IN THE MOST MONEY?",
        loc="left",
        pad=20
    )

    ax.set_xlabel("Average worldwide revenue (USD billions)")
    ax.set_ylabel("")

    ax.grid(axis="x", alpha=0.15)
    ax.set_axisbelow(True)

    # Annotate each bar with its value just past the bar tip
    for bar, value in zip(
        bars,
        df4["avg_revenue"] / 1_000_000_000
    ):
        ax.text(
            bar.get_width() + 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"${value:.2f}B",
            va="center",
            fontsize=9
        )

    add_source_note()
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(
        "visualizations/Q4_Revenue_by_Genre.png",
        bbox_inches="tight"
    )
    plt.close()

    # -----------------------------------------------------
    # Q5A: TOP 10 HIGHEST‑GROSSING FILMS
    # -----------------------------------------------------

    print("\n5A. Top 10 highest-grossing films")

    # SQL: get the 10 movies with the highest revenue, requiring at least 1000 votes
    # to filter out obscure titles with unreliable data.
    query_5_revenue = text("""
        SELECT
            title,
            revenue,
            vote_average,
            vote_count
        FROM movies
        WHERE revenue > 10000
          AND vote_count > 1000
        ORDER BY revenue DESC
        LIMIT 10;
    """)

    df5_revenue = pd.read_sql(query_5_revenue, engine)
    print(df5_revenue.to_string(index=False))

    # --- PLOT 5A: Horizontal bar chart of top grossing films ---
    # Sort ascending so the #1 film appears at the top
    df5_rev_plot = df5_revenue.sort_values("revenue", ascending=True)

    fig, ax = plt.subplots(figsize=(11, 7))

    bars = ax.barh(
        df5_rev_plot["title"],
        df5_rev_plot["revenue"] / 1_000_000_000,
        color="#D9D9D9"
    )

    # Highlight the highest‑grossing film (top bar) in red
    bars[-1].set_color("#C62828")

    ax.set_title(
        "TOP 10 HIGHEST-GROSSING FILMS",
        loc="left",
        pad=20
    )

    ax.set_xlabel("Worldwide revenue (USD billions)")
    ax.set_ylabel("")

    ax.grid(axis="x", alpha=0.15)
    ax.set_axisbelow(True)

    # Add value labels
    for bar, value in zip(
        bars,
        df5_rev_plot["revenue"] / 1_000_000_000
    ):
        ax.text(
            bar.get_width() + 0.03,
            bar.get_y() + bar.get_height() / 2,
            f"${value:.1f}B",
            va="center",
            fontsize=9
        )

    add_source_note()
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(
        "visualizations/Q5A_Top10_Highest_Grossing.png",
        bbox_inches="tight"
    )
    plt.close()

    # -----------------------------------------------------
    # Q5B: TOP 10 HIGHEST‑RATED FILMS
    # -----------------------------------------------------

    print("\n5B. Top 10 highest-rated films")

    # SQL: get the 10 movies with the highest vote_average, again requiring >1000 votes
    query_5_rating = text("""
        SELECT
            title,
            revenue,
            vote_average,
            vote_count
        FROM movies
        WHERE revenue > 10000
          AND vote_count > 1000
        ORDER BY vote_average DESC
        LIMIT 10;
    """)

    df5_rating = pd.read_sql(query_5_rating, engine)
    print(df5_rating.to_string(index=False))

    # --- PLOT 5B: Horizontal bar chart of top rated films ---
    df5_rating_plot = df5_rating.sort_values(
        "vote_average",
        ascending=True
    )

    fig, ax = plt.subplots(figsize=(11, 7))

    bars = ax.barh(
        df5_rating_plot["title"],
        df5_rating_plot["vote_average"],
        color="#D9D9D9"
    )

    bars[-1].set_color("#C62828")

    ax.set_title(
        "TOP 10 HIGHEST-RATED FILMS",
        loc="left",
        pad=20
    )

    ax.set_xlabel("TMDb audience rating")
    ax.set_ylabel("")

    # Zoom the x‑axis to the relevant rating range, but keep the upper bound at 10
    ax.set_xlim(
        max(0, df5_rating_plot["vote_average"].min() - 0.5),
        10
    )

    ax.grid(axis="x", alpha=0.15)
    ax.set_axisbelow(True)

    # Label each bar with the rating value (one decimal)
    for bar, value in zip(
        bars,
        df5_rating_plot["vote_average"]
    ):
        ax.text(
            bar.get_width() + 0.03,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.1f}",
            va="center",
            fontsize=9
        )

    add_source_note()
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(
        "visualizations/Q5B_Top10_Highest_Rated.png",
        bbox_inches="tight"
    )
    plt.close()

    # -----------------------------------------------------
    # Q5C: OVERLAP ANALYSIS
    # How many movies appear in both the highest‑grossing and highest‑rated lists?
    # -----------------------------------------------------
    # Convert the title columns of both DataFrames into Python sets for fast set operations
    revenue_titles = set(df5_revenue["title"])
    rating_titles = set(df5_rating["title"])

    # Find titles that are present in both sets (intersection)
    overlap = revenue_titles.intersection(rating_titles)

    print("\n5C. Top 10 overlap")
    print(f"Overlap: {len(overlap)} / 10")
    print("Overlapping titles:")

    # Print each overlapping title in alphabetical order
    for movie in sorted(overlap):
        print(f"- {movie}")

    # Calculate and display the overlap percentage
    overlap_percentage = (len(overlap) / 10) * 100
    print(
        f"\nOnly {len(overlap)} of the top 10 titles "
        f"appear in both lists ({overlap_percentage:.0f}%)."
    )

    print(
        "\nSuccess! Presentation-ready charts saved in "
        "the 'visualizations' folder."
    )


# ==========================================
# 6. MAIN EXECUTION BLOCK
# ==========================================

# Similar to concept to main() in ANSI C,
# This standard Python idiom ensures the pipeline functions are called only when
# this script is executed directly (not when imported as a module).
if __name__ == "__main__":
    # Run the ETL pipeline to populate the database with fresh data
    run_etl_pipeline()
    # Perform the analysis and generate all charts
    run_analysis()