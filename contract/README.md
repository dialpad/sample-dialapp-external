# contract

`openapi.json` is the contract between Dialpad, a partner rightbar app's backend and
the frontend SDK, as an OpenAPI 3.1 document. It is language-neutral: any backend
that implements it works with the SDK. It describes:

- the endpoints a backend exposes: the panel page (`GET /`, with the idtoken in the
  query), `GET /dialpad/ext-connection`, `POST /dialpad/ext-disconnect` and the
  OAuth callback (its path is yours to choose). The SDK always calls the two
  `/dialpad` endpoints at those paths;
- the schemas: the decoded idtoken's claims (`IdTokenClaims`), the page data the
  page embeds for the SDK (`PageData`), the connection status
  (`ExternalConnection`) and the error body (`ErrorResponse`).

The partner's own feature endpoints (such as this app's `POST /api/contact`) sit
beside these and are not part of the contract.

It is generated, so don't edit it by hand. Its `info.version` is the SDK version it
describes, so check it against the SDK version that `client/pnpm-lock.yaml` resolves. The server's
`acme_dialpad_rightbar/dialpad/contract.py` is this app's Python implementation of the same
schemas.
