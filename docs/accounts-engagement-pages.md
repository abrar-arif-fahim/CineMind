# Accounts, ratings and watchlist: backend ↔ frontend contract

Sprint: 23–29 November. This file lists the routes, template names and
variables the backend provides, plus ready-made form snippets. If a name
needs to change, agree on it first and update this file in the same PR.

## How we avoid merge conflicts

- **Backend** changes Python files, `config/`, migrations, and adds one line
  to `templates/base.html` (`{% include "includes/messages.html" %}` inside
  `<main>`). Please keep that line.
- **Frontend** works only in `templates/` and `static/`. The backend ships
  plain starter templates inside the apps (`accounts/templates/accounts/…`,
  `engagement/templates/engagement/…`). A file with the **same name** in the
  project `templates/` folder replaces the starter one automatically, so
  create yours at:
  - `templates/accounts/login.html`
  - `templates/accounts/register.html`
  - `templates/accounts/profile.html`
  - `templates/engagement/watchlist.html`
- Frontend edits in `base.html` (navbar) and `catalogue/movie_detail.html`
  (rating/watchlist panels) use the snippets below.

## Pages

| Page            | URL                    | URL name               | Template                     | Login |
|-----------------|------------------------|------------------------|------------------------------|-------|
| Register        | `/accounts/register/`  | `accounts:register`    | `accounts/register.html`     | –     |
| Log in          | `/accounts/login/`     | `accounts:login`       | `accounts/login.html`        | –     |
| Profile         | `/accounts/profile/`   | `accounts:profile`     | `accounts/profile.html`      | yes   |
| Watchlist       | `/watchlist/`          | `engagement:watchlist` | `engagement/watchlist.html`  | yes   |

Logged-in users who open Register or Log in are sent to the homepage.
Pages that need a login send visitors to `/accounts/login/?next=<page>`.

## Actions (forms with `method="post"` and `{% csrf_token %}`)

All of them need a logged-in user, accept **POST only** (GET returns 405) and
only change the logged-in user's own data. After the action the user goes
back to the movie page, or to a `next` field if the form sends one (only
addresses on our own site are accepted). Each action leaves a message.

| Action                 | URL                              | URL name (arg: movie pk)          | Fields          |
|------------------------|----------------------------------|-----------------------------------|-----------------|
| Log out                | `/accounts/logout/`              | `accounts:logout`                 | –               |
| Rate / change rating   | `/movies/<pk>/rate/`             | `engagement:rate_movie`           | `score` (1–5)   |
| Remove my rating       | `/movies/<pk>/rate/delete/`      | `engagement:delete_rating`        | –               |
| Add to watchlist       | `/movies/<pk>/watchlist/add/`    | `engagement:add_to_watchlist`     | –               |
| Remove from watchlist  | `/movies/<pk>/watchlist/remove/` | `engagement:remove_from_watchlist`| –               |

Visitors who are not logged in and submit one of these forms are sent to the
login page and come back to the movie afterwards.

## Form fields and variables

**Register** (`form`): `username`, `email`, `password1`, `password2`; `next`.
Errors: `form.non_field_errors`, `form.<field>.errors`. Password rules: at
least 8 characters, not too common, not only digits, not too similar to the
username.

**Log in** (`form`): `username`, `password`; `next` (put it in a hidden input).
Wrong password → `form.non_field_errors`.

**Profile** (`user` is always available in templates):

| Variable           | What it is                                            |
|--------------------|-------------------------------------------------------|
| `rating_count`     | number of movies the user rated                       |
| `average_score`    | the user's average score, or `None`                   |
| `watchlist_count`  | number of saved movies                                |
| `recent_ratings`   | up to 5 latest ratings: `rating.movie`, `rating.score`, `rating.updated_at` |
| `recent_watchlist` | up to 4 latest saved: `entry.movie`, `entry.added_at` |

**Watchlist**:

| Variable          | What it is                                                     |
|-------------------|----------------------------------------------------------------|
| `entries`         | this page's entries, newest first: `entry.movie` (with `genres.all`), `entry.added_at` |
| `watchlist_count` | total saved movies                                             |
| `page_obj`        | pagination, 12 per page (same as the catalogue)                |

**Movie details** (added to the existing variables):

| Variable              | What it is                                           |
|-----------------------|------------------------------------------------------|
| `user_rating`         | the logged-in user's score (1–5), or `None`          |
| `in_watchlist`        | `True` if the logged-in user saved this movie         |
| `rating_choices`      | `[1, 2, 3, 4, 5]`                                     |
| `movie.average_rating`| average of all users' scores, or `None`              |
| `movie.rating_count`  | how many users rated it                               |

Every movie also has `movie.get_absolute_url` (its detail page).

**Messages**: `templates/includes/messages.html` shows them as Bootstrap
alerts. Tags: `success`, `info`, `error`.

## Snippets

### Navbar (`base.html`): replace the disabled Watchlist / Login / Register items

```django
{% if user.is_authenticated %}
<li class="nav-item">
    <a class="nav-link{% if request.resolver_match.view_name == 'engagement:watchlist' %} active{% endif %}" href="{% url 'engagement:watchlist' %}">Watchlist</a>
</li>
<li class="nav-item">
    <a class="nav-link{% if request.resolver_match.view_name == 'accounts:profile' %} active{% endif %}" href="{% url 'accounts:profile' %}">{{ user.username }}</a>
</li>
<li class="nav-item">
    <form method="post" action="{% url 'accounts:logout' %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-link nav-link">Log out</button>
    </form>
</li>
{% else %}
<li class="nav-item"><a class="nav-link" href="{% url 'accounts:login' %}?next={{ request.path|urlencode }}">Login</a></li>
<li class="nav-item"><a class="nav-link register-link" href="{% url 'accounts:register' %}">Register</a></li>
{% endif %}
```

### Movie details: rating panel

```django
<section class="movie-detail-panel p-3 h-100" aria-labelledby="rating-title">
    <h2 id="rating-title" class="h5">Your rating</h2>
    {% if movie.rating_count %}
    <p class="home-description small">Average {{ movie.average_rating|floatformat:1 }}/5 from {{ movie.rating_count }} rating{{ movie.rating_count|pluralize }}</p>
    {% endif %}
    {% if user.is_authenticated %}
    <form method="post" action="{% url 'engagement:rate_movie' movie.pk %}">
        {% csrf_token %}
        <fieldset class="d-flex flex-wrap gap-2 mb-2">
            <legend class="visually-hidden">Rate {{ movie.title }} from 1 to 5</legend>
            {% for score in rating_choices %}
            <input type="radio" class="btn-check" name="score" id="score-{{ score }}" value="{{ score }}"{% if score == user_rating %} checked{% endif %} required>
            <label class="btn catalogue-outline-btn" for="score-{{ score }}">{{ score }}</label>
            {% endfor %}
        </fieldset>
        <button type="submit" class="btn home-browse-btn">{% if user_rating %}Update rating{% else %}Save rating{% endif %}</button>
    </form>
    {% if user_rating %}
    <form method="post" action="{% url 'engagement:delete_rating' movie.pk %}" class="mt-2">
        {% csrf_token %}
        <button type="submit" class="btn btn-link p-0">Remove my rating</button>
    </form>
    {% endif %}
    {% else %}
    <a href="{% url 'accounts:login' %}?next={{ request.path|urlencode }}">Log in to rate this movie</a>
    {% endif %}
</section>
```

### Movie details: watchlist panel

```django
<section class="movie-detail-panel p-3 h-100" aria-labelledby="watchlist-title">
    <h2 id="watchlist-title" class="h5">Your watchlist</h2>
    {% if user.is_authenticated %}
    <form method="post" action="{% if in_watchlist %}{% url 'engagement:remove_from_watchlist' movie.pk %}{% else %}{% url 'engagement:add_to_watchlist' movie.pk %}{% endif %}">
        {% csrf_token %}
        <button type="submit" class="btn catalogue-outline-btn">{% if in_watchlist %}Remove from Watchlist{% else %}Add to Watchlist{% endif %}</button>
    </form>
    {% else %}
    <a href="{% url 'accounts:login' %}?next={{ request.path|urlencode }}">Log in to save this movie</a>
    {% endif %}
</section>
```

### Remove button on the watchlist page (returns to the same page)

```django
<form method="post" action="{% url 'engagement:remove_from_watchlist' entry.movie.pk %}">
    {% csrf_token %}
    <input type="hidden" name="next" value="{{ request.get_full_path }}">
    <button type="submit" class="btn catalogue-outline-btn btn-sm">Remove</button>
</form>
```

## Trying it

```
python manage.py migrate
python manage.py load_sample_movies
python manage.py runserver
```
Create an account at `/accounts/register/`, then rate a movie and save it.
Run all tests with `python manage.py test`.
