"""The Dialpad contract: what Dialpad and its SDK need from this server.

* ``idtoken.py``: decodes the idtoken Dialpad adds to the panel page's URL.
* ``contract.py``: the models the SDK reads (the page data, the connection, errors).
* ``panel_page.py``: renders the panel page, its page data and its Content-Security-Policy.
* ``endpoints/``: ``GET /`` (the panel page), ``GET /dialpad/ext-connection`` and
  ``POST /dialpad/ext-disconnect``.

A server in another language ports this package (chapter 1 of the guide). ``contract/openapi.json``
describes the same contract.
"""
