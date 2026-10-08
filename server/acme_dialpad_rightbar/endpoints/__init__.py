"""The server's HTTP endpoints, one file each, in two folders by who calls them.

* ``dialpad/``: the endpoints of the DialApp contract. Dialpad, or the SDK it ships, calls these:
  the panel page, ``ext-connection`` and ``ext-disconnect``.
* ``app/``: the application's own endpoints: the routes its iframe panel adds for itself (such as
  ``POST /api/contact``), the OAuth screens that stand in for a CRM, and development helpers.

Each file defines one ``register(app, ctx)`` that adds its route, and each folder's ``__init__.py``
lists them. ``acme_dialpad_rightbar.app.create_app`` calls the two folders'
``register_*_endpoints``.
"""
