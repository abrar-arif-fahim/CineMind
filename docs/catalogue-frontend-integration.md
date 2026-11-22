# Catalogue frontend integration

The template is `catalogue/movie_list.html`. No catalogue or movie-detail view or
route currently exists. Backend files were left unchanged for Burak to integrate.

## Required view contract

- Use GET parameters `q` (title search), `genre` (Genre primary key), `year`
  (release year), and `page` (page number).
- Validate genre/year inputs; apply title matching to `Movie.title`, genre matching
  to `Movie.genres`, and year matching to `Movie.release_date`.
- Supply `movies`: the current page of actual Movie records. Prefetch `genres`.
- Supply `genres`: Genre records for the dropdown, including all available genres
  even when the movie results are filtered.
- Supply `page_obj`: a Django Paginator Page for the filtered, consistently ordered
  queryset. Set `movies` to `page_obj.object_list`. Pagination appears only when
  multiple pages exist. The template's built-in `querystring` tag preserves GET
  parameters and replaces `page`.
- Optionally supply `movie_detail_url_name`: the name of an existing detail route
  accepting `pk`. The template reverses this route per movie and shows View Details
  only when reversal succeeds. Otherwise it shows Details coming soon.
- Render with the request so the configured request context processor supplies
  form values, the current path and pagination query parameters.

No catalogue URL name is assumed. The GET form and Clear Filters link use the
current path. Agree a catalogue URL/name with Burak, then connect the Movies
navigation item in base.html and the Browse Movies button in home.html.
The existing `home` URL is required by base.html.

## Browser verification after backend integration

1. Activate `.venv`, run `python manage.py check`, then `python manage.py runserver`.
2. Open the catalogue URL registered by Burak.
3. Test title, genre and year separately and together. Confirm selected values stay
   visible and Clear Filters removes all query parameters.
4. With enough existing records, navigate pages and confirm filters remain in the
   URL. Confirm a new search starts at page one.
5. Test no matches, missing metadata/posters, and details links after a route exists.
6. Check 375px, tablet and desktop widths, keyboard focus, form labels, and mobile
   navigation. Bootstrap assets require access to the CDN used by base.html.

Until a catalogue route/view is connected, there is no live catalogue URL to open.
The template can be rendered independently for frontend verification without
creating database records.

## Movie details frontend integration

The details template is `catalogue/movie_detail.html`. Backend files remain
unchanged; a details view and route still need to be connected by Burak.

- Required context: `movie`, the selected actual Movie instance. Look it up by
  primary key, prefetch its `genres`, and return HTTP 404 for an unknown movie.
  Render the template with the request.
- Fields used: `title`, `release_date`, `runtime`, `overview`, `poster_url`
  (existing property based on `poster_path`), and `genres.all` / Genre `name`.
  Missing metadata has readable fallbacks. Overview text stays HTML-escaped.
- Required detail route contract: accept an integer keyword argument named `pk`.
  Suggested path/name for agreement: `/movies/<int:pk>/`, named
  `catalogue:movie_detail` if Burak introduces a `catalogue` namespace. These are
  proposals, not registered routes.
- The catalogue view must pass the actual registered detail route name as
  `movie_detail_url_name`, preserving the existing optional contract. The list
  template reverses that name using `pk=movie.pk`.
- Optional details context: `movie_list_url_name`, the actual registered catalogue
  route name, reversible without arguments. The Back to Movies link appears only
  when this name is supplied and reversal succeeds. No route name is hardcoded.
- Rating and watchlist areas are frontend placeholders with native disabled
  buttons. They have no forms, endpoints, user-state assumptions or event handlers.
  Burak must define rating scale, current user rating, watchlist membership,
  authentication rules and CSRF-protected write endpoints before enabling them.
  No engagement logic was added.

After integration, open an existing movie through the catalogue's View Details
link. Check full and missing metadata, missing/broken posters, the Back to Movies
link, escaped synopsis text, disabled engagement controls, and a nonexistent movie
returning 404. Verify 375px, tablet and desktop layouts. Until the view and route
exist, the details page has no live browser URL.
