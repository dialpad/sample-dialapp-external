"""Everything demo-only: replace or delete it, don't ship it.

The demo has no database and no real CRM, so it fakes the parts that need them, and it adds a few
extras a real app doesn't need. They all live here, so the rest of the server holds no fake code:

* ``fake_storage.py``: the stand-in for a database, kept in each browser's cookie. The route
  handlers use it as ``ctx.storage``; a real app swaps in its own database.
* ``oauth_results.py``: the in-memory note the OAuth callback leaves for the iframe panel. A real
  app stores the CRM tokens in its callback instead, and needs no note.
* ``oauth.py``: the fake consent screen that stands in for the CRM's.
* ``dialpad_api.py``: the demo call to Dialpad's public API on the page request.
* ``endpoints/``: the routes only the demo has: the fake authorize page, ``/healthz`` for the
  browser tests, and the local-mode dev route.

Every import from this package in the rest of the server marks a place to put the real thing;
chapter 11 of the guide lists them.
"""
