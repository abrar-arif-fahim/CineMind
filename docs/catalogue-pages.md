# Catalogue pages: backend ↔ frontend contract

This file lists what the backend gives each page, so the frontend templates
can use it without guessing. If a name needs to change, agree on it first and
update this file in the same pull request.

The styled templates live in the project's `templates/` directory.

## Pages

| Page           | URL                  | URL name                    | Template                         |
|----------------|----------------------|-----------------------------|----------------------------------|
| Homepage       | `/`                  | `catalogue:home`            | `catalogue/home.html`            |
| Movie catalogue| `/movies/`           | `catalogue:movie_list`      | `catalogue/movie_list.html`      |
| Movie details  | `/movies/<id>/`      | `catalogue:movie_detail`    | `catalogue/movie_detail.html`    |

All three extend `templates/base.html` and fill
`{% block title %}` and `{% block content %}`.

Links in templates: `{% url 'catalogue:home' %}`,
`{% url 'catalogue:movie_list' %}`, `{% url 'catalogue:movie_detail' movie.pk %}`.

## A movie object

Every `movie` in the variables below has:

| Field                 | Example                       | Notes                                         |
|-----------------------|-------------------------------|-----------------------------------------------|
| `movie.pk`            | `6`                           | use in the detail URL                         |
| `movie.title`         | `Inception`                   |                                               |
| `movie.overview`      | `A thief who…`                | may be empty                                  |
| `movie.release_date`  | date                          | may be empty; format with `\|date:"j F Y"`    |
| `movie.release_year`  | `2010`                        | `None` when there is no date                  |
| `movie.runtime`       | `148`                         | minutes; may be empty                         |
| `movie.poster_url`    | `https://image.tmdb.org/…jpg` | empty string when there is no poster: show a placeholder |
| `movie.genres.all`    | list of genres                | each has `genre.pk` and `genre.name`; already loaded, no extra queries |

## Homepage – `catalogue/home.html`

| Variable        | What it is                                                        |
|-----------------|-------------------------------------------------------------------|
| `latest_movies` | up to 8 movies, newest release first                              |
| `genres`        | genres that have movies, A–Z; each also has `genre.movie_count`   |
| `movie_count`   | number of movies in the catalogue (0 = show an "empty" message)   |

Link a genre to its filtered list with
`{% url 'catalogue:movie_list' %}?genre={{ genre.pk }}`.

## Movie catalogue – `catalogue/movie_list.html`

The search and filter form must use **method `get`** and these field names:

| Field name | Value                      | Example         |
|------------|----------------------------|-----------------|
| `q`        | text searched in the title | `?q=matrix`     |
| `genre`    | a genre's `pk`             | `?genre=6`      |
| `year`     | a release year             | `?year=1999`    |
| `page`     | page number (12 per page)  | `?page=2`       |

All are optional and can be combined. A bad value (unknown genre, `year=abc`,
a page past the end) never causes an error: it is ignored, or the nearest
valid page is shown.

| Variable          | What it is                                                         |
|-------------------|--------------------------------------------------------------------|
| `movies`          | the movies on the current page (A–Z by title)                      |
| `result_count`    | how many movies match in total (all pages)                         |
| `genres`          | all genres, A–Z, for the genre dropdown                            |
| `years`           | years that have movies, newest first, for the year dropdown        |
| `query`           | the current search text (`""` if none), to refill the search box   |
| `selected_genre`  | the chosen genre object, or `None`; compare with `genre == selected_genre` |
| `selected_year`   | the chosen year as a number, or `None`; compare with `year == selected_year` |
| `is_filtered`     | `True` when a search or filter is active (for "Clear filters" and the "no results" message) |
| `is_paginated`    | `True` when there is more than one page                            |
| `page_obj`        | Django page: `number`, `has_previous`, `has_next`, `previous_page_number`, `next_page_number`, `paginator.num_pages` |
| `form`            | the same options as a Django form, if you prefer `{{ form.q }}` etc. |

Page links that keep the current search and filters:
`<a href="{% querystring page=page_obj.next_page_number %}">Next</a>`.

Three states to design: results, **no results for a search**
(`not movies and is_filtered`) and **empty catalogue** (`not movies and not is_filtered`).

## Movie details – `catalogue/movie_detail.html`

| Variable | What it is                                     |
|----------|------------------------------------------------|
| `movie`  | the movie (fields above)                       |

An unknown id returns Django's normal 404 page.

## Test data

```
python manage.py migrate
python manage.py load_sample_movies   # 15 movies, 14 genres; safe to re-run
python manage.py runserver
```

Run the tests with `python manage.py test catalogue`.
