# 7. Show the CRM record

Dialpad tells the panel which contact is open, but that's _Dialpad's_ contact: a
name, phone numbers, and emails from Dialpad's directory. Your panel exists to
show _your_ record for that person. Finding one from the other is the _contact
mapping_, and it runs on your server, because it needs the user's CRM tokens.

## The flow

```mermaid
sequenceDiagram
  autonumber
  participant D as Dialpad host
  participant P as Panel
  participant S as Your server (/api/contact)
  participant DB as Database
  participant C as Acme CRM

  D-->>P: A contact opens (state.contact), or a call brings its own (state.call.contact)
  P->>P: Show loading, and remember which contact this lookup is for
  P->>S: POST /api/contact with the contact (Bearer)
  S->>DB: CRM tokens for this user?
  alt None
    S-->>P: 403 not_connected
  else Present
    S->>C: Refresh the access token if it expired
    S->>DB: Mapping for this Dialpad contact?
    alt Mapped
      S->>C: GET the record (Bearer CRM token)
    else Not mapped
      S->>C: Search by phone numbers and emails
      C-->>S: Zero, one, or several matches
      S->>DB: Save the mapping for the one chosen
    end
    C-->>S: The record
    S-->>P: 200 with only the fields the panel shows
  end
  alt Still the open contact
    P->>P: Show the record
    P->>D: linkRecord({ type, url })
  else Another contact opened meanwhile
    P->>P: Ignore this answer
  end
```

## On your server

`POST /api/contact` is your own route ([chapter 5](05-authenticate-requests.md#add-your-own-routes)),
not part of the contract, so its path and shape are yours. After authenticating
the request:

```mermaid
flowchart TD
  A["POST /api/contact"] --> B{"CRM tokens stored<br/>for this Dialpad user?"}
  B -- no --> N["403 not_connected"]
  B -- yes --> R{"Access token expired?"}
  R -- yes --> RF["Refresh it. If the CRM says<br/>the grant is revoked, delete the tokens"]
  R -- no --> M
  RF --> M{"Mapping saved for this<br/>Dialpad contact?"}
  M -- yes --> F["Fetch the mapped record<br/>with the CRM token"]
  M -- no --> Q["Search the CRM by phone numbers<br/>and emails"]
  Q --> X{"How many matches?"}
  X -- one --> S1["Save the mapping"] --> F
  X -- several --> PK["Let the user pick,<br/>then save the mapping"] --> F
  X -- none --> CR["Offer to create a record"]
  F --> O["Return only the fields the panel shows<br/>(never the CRM token)"]
```

1. **Check the connection.** No CRM tokens means not connected: answer `403`, and
   the panel offers to connect.
2. **Map the contact.** Look in your mapping table first. Otherwise, search the
   CRM by the contact's phone numbers and emails, in the form the CRM stores
   (usually E.164 phone numbers and lowercase emails), and decide what zero, one,
   and several matches mean. Save the choice.
3. **Fetch the record** with `Authorization: Bearer <CRM access token>`. Return
   only the fields the panel shows, and the record's type and URL in the CRM, for
   [`linkRecord`](#link-the-record-in-dialpad).
4. **Handle a slow or failing CRM** with a short timeout and an error the panel
   can show.

## In the panel

- **Ignore late answers.** The user can open another contact before the lookup
  finishes. Number each lookup, and show an answer only if it belongs to the
  latest one.
- **Show both contacts during a call when they differ.** There can be two: the
  panel's (`state.contact`) and the call's own (`state.call.contact`). Usually
  they're the same person, and one section is enough.
- **Show loading and failure.** This app also shows an error toast when a lookup
  fails.

## Link the record in Dialpad

Once the panel has the record, tell Dialpad about it with `linkRecord`:

```ts
await rightbar.linkRecord({
  type: "Contact",
  url: "https://crm.example/contacts/42",
});
await rightbar.linkRecord(null); // unlink, for example when another contact opens
```

Dialpad then:

- Shows a **View Contact** button (with your `type`) in the panel's header, which
  opens `url` in a new tab. It shows only while the user is connected and the
  panel menu has **Disconnect**.
- Uses `url` as the default for screen pops (below).
- Changes the panel menu.

Unlink with `linkRecord(null)` as soon as the contact changes, when the lookup
fails, and when the user disconnects, so Dialpad never shows a record for another
contact. Link only the panel's own contact, not a call's other contact: Dialpad
keeps one linked record per panel.

### The panel menu

The panel menu is Dialpad's menu in your panel's header. What it holds depends on
`linkRecord`:

1. Before the user connects, there's no menu.
2. Once connected, with no record linked, the menu has only **Disconnect**.
3. Once a record is linked, the menu is your app's own entry in Dialpad's menu
   configuration. Dialpad finds it by your app's name in lowercase, with the first
   space replaced by `_`. An app without an entry gets an empty menu, which also
   hides the **View Contact** button.

So ask Dialpad to set up your app's menu entry before you link records. The entry
can offer **Rematch** and **Create Task** as well as **Disconnect**. Your
panel hears about them through events:

| Call                                             | What it does                                                                                                           |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `linkRecord({ type, url })` / `linkRecord(null)` | Tells Dialpad which of your records matches the open contact, or unlinks it                                            |
| `on('rematch' \| 'createTask', callback)`        | Runs `callback` when the user picks **Rematch** or **Create Task** in the panel menu. Returns a function that stops it |
| `screenPop({ url?, force? })`                    | Asks Dialpad to open a record for the active call, by default the linked record's URL                                  |

### Screen pops

A _screen pop_ opens the caller's record when a call comes in.
`rightbar.screenPop()` asks Dialpad to open the linked record's URL, or the `url`
you pass. Without `force`, Dialpad pops only when the user has screen pops turned
on, during a live inbound call, at most once per call, and not for an office or
department contact.

## In this demo

- There's no CRM, so there's no mapping. `POST /api/contact`
  (`server/acme_dialpad_rightbar/endpoints/app/contact.py`) returns every
  non-empty field of the Dialpad contact with an `Acme ` prefix. That proves the
  contact reached the server and came back, for the right user. The route's
  docstring describes what a real one does.
- The route also returns a record to link: a page labelled fake at
  `/records/<contact id>` (`server/acme_dialpad_rightbar/fake_record.py`), which
  stands in for the CRM's page for the record and shows only the contact's ID.
- `client/src/components/AcmeContact.vue` runs the lookup, shows loading and
  failure, and ignores late answers. Once the lookup succeeds, it links the
  record, and it unlinks as described above.

---

**Previous:** [6. Connect the user to the CRM](06-connect-to-the-crm.md) ·
**Next:** [8. Call Dialpad's API and receive events](08-call-dialpad.md) ·
[Contents](../README.md#the-guide)
