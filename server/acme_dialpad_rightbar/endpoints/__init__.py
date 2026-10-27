"""The HTTP endpoints a real app keeps, one file each, in two folders by who calls them.

* ``dialpad/``: the endpoints of the DialApp contract. Dialpad, or the SDK it ships, calls these:
  the panel page, ``ext-connection`` and ``ext-disconnect``.
* ``app/``: the application's own endpoints, such as the OAuth callback.

Each file defines one ``register(app, ctx)`` that adds its route, and each folder's ``__init__.py``
lists them. The CRM record's routes are in ``acme_dialpad_rightbar.crm``, and the routes only the
demo has in ``acme_dialpad_rightbar.demo.endpoints``. ``acme_dialpad_rightbar.app.create_app``
calls each folder's ``register_*_endpoints``.
"""
