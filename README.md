# JDE10_Interim_Project

## Description
- A ETL Pipeline that extracts movie data from the TMDB website's API, transforms it into a suitable format and loads it into a PostgreSQL database.
- TMDB API is obtained from personal TMDB account and used in GET requests.
- Queries are made to database to determine what affects box office performance.
  - Release timing
  - Original movies or franchise films
  - Duration of movies
  - Best selling genres
  - Correlation between highest grossing films and their ratings

## Notes
- The Project uses sensitive information in its coding variables; the code shown here is modified to avoid compromising related accounts
  - API Key
  - Password from DBI URL for connecting to PostgreSQL
