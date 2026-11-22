// Replace unavailable posters, including images that failed before this script loaded.
document.querySelectorAll('.movie-poster[data-fallback-src]').forEach(function (poster) {
    function showPlaceholder() {
        poster.removeEventListener('error', showPlaceholder);
        poster.src = poster.dataset.fallbackSrc;
        poster.alt = 'Poster unavailable';
    }

    poster.addEventListener('error', showPlaceholder);
    if (poster.complete && poster.naturalWidth === 0) {
        showPlaceholder();
    }
});
