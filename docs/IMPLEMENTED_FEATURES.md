# What Has Been Implemented

This note explains the cinema booking project features in a simple, step-by-step way.

## 1. User types

The system has three kinds of users:

- **Super Admin**: manages all cinemas and approves or rejects cinema registrations.
- **Tenant Admin**: manages the cinema they own.
- **User**: can browse cinemas that have been approved and are active.

## 2. Accounts and sign-in

People can create a regular user account and sign in to receive access tokens. The system uses these tokens to recognize users on protected API requests.

- A public registration request creates a regular **User** account.
- A **Super Admin** can create a **Tenant Admin** account.
- Signing in returns tokens that include the user's role.
- A signed-in user can view their own account details.
- Only a **Super Admin** can view another user's account details.
- Users can sign out or request a refreshed access token.

## 3. Cinema registration

A cinema owner can register a cinema and a tenant-admin account together. The cinema starts with **Pending** status, so it is not shown to regular users until a Super Admin approves it.

Cinema details include its name, web domain, address, city, and contact information. The system also creates identifying cinema details automatically.

## 4. Cinema APIs and access

All cinema routes start with `/api/cinemas/`.

| Action | API | Who can use it |
|---|---|---|
| Register a cinema and its owner | `POST /api/cinemas/register/` | Anyone |
| List cinemas | `GET /api/cinemas/` | Signed-in users; results depend on role |
| Create a cinema through the management API | `POST /api/cinemas/` | Super Admin |
| View one cinema | `GET /api/cinemas/{id}/` | Super Admin; its Tenant Admin; or any user if the cinema is active |
| Change cinema details | `PUT` or `PATCH /api/cinemas/{id}/` | Super Admin or that cinema's Tenant Admin |
| Delete a cinema | `DELETE /api/cinemas/{id}/` | Super Admin |
| Approve a cinema | `POST /api/cinemas/{id}/approve/` | Super Admin |
| Reject a cinema | `POST /api/cinemas/{id}/reject/` | Super Admin |

For protected requests, include the access token in the request header:

```text
Authorization: Bearer <access_token>
```

### What each role can see

- **Super Admin** can see all cinemas.
- **Tenant Admin** can see only the cinema they own.
- **User** can see only active cinemas.

Tenant Admins cannot delete cinemas or approve/reject them. Regular users cannot create, change, or delete cinemas.

## 5. Approval and cinema status

Cinema registrations begin as **Pending**. A Super Admin can:

- **Approve** a cinema, changing its status to **Active**.
- **Reject** a cinema, changing its status to **Rejected**.

Only active cinemas are visible to regular users.

## 6. Automated checks

## 6. Movie catalogue

Movies are stored in the linked cinema's PostgreSQL schema. Each movie has a title, description, duration in minutes, language, genre, release date, and Draft, Active, or Inactive status. New movies always start as Draft.

- For registration, a Tenant Admin sends the cinema schema in the `X-Schema-Name` header. The server verifies that the schema belongs to that account and saves the movie in that cinema.
- For listing, a Tenant Admin gets only their own cinema's movies; a Super Admin may send `X-Schema-Name` to list one cinema or omit it to list across cinemas.
- Tenant Admins can create, update, and delete movies only for their own cinema. They can change a movie from Draft to Active when it is ready.
- Super Admins can view all movies but cannot create, update, or delete them.
- Regular users can view Active movies only in Active cinemas.
- The movie APIs support create, list, view, update, and delete.
- Movie IDs are allocated across cinema schemas. A detail request returns `409 Conflict` if it finds the same ID in multiple schemas.

## 7. Screen setup

Screen, Seat, Show, and show-specific seat-price tables are stored in each cinema's PostgreSQL schema. All screen, layout, show, and price APIs require a Tenant Admin access token. The server derives the cinema and schema from the authenticated Tenant Admin's cinema record; do not send a schema in the body or an `X-Schema-Name` header.

| Action | API | Description |
|---|---|---|
| Create a screen | `POST /api/shows/screens/` | Body: `name`, `total_seats`; cinema is assigned from the authenticated account |
| List screens | `GET /api/shows/screens/` | Lists the signed-in Tenant Admin's screens |
| Configure a permanent screen layout | `POST /api/shows/screens/{id}/configure-layout/` | Generates seats once with row, number, type, and gap positions |
| Retrieve seats in a screen | `GET /api/shows/screens/{id}/seats/` | Returns the permanent screen layout |
| Create a show | `POST /api/shows/` | Links a same-cinema movie and configured screen with a date and start/end times |
| List shows | `GET /api/shows/` | Lists shows for the signed-in Tenant Admin's cinema |
| View a show | `GET /api/shows/{id}/` | Returns scheduled show details |
| Set or change prices for a show | `PUT /api/shows/{id}/prices/` | Replaces the prices for all seat categories used by that screen |
| Retrieve show prices | `GET /api/shows/{id}/prices/` | Returns that show's category prices |
| Retrieve seats with a show's prices | `GET /api/shows/{id}/seats/` | Returns permanent seats with prices from the selected show |

Layout requests include a `rows` array with each row's `label`, `seat_count`, and `seat_type`; optional `gaps_after` values insert aisle gaps after the specified seat positions. Supported types are `NORMAL`, `GOLD`, `PREMIUM`, and `RECLINER`. The generated seat count must equal the screen capacity, and duplicate row labels and seat numbers are rejected. The layout can only be configured once; subsequent attempts to change it are rejected.

Show requests include `movie`, `screen`, `show_date`, `start_time`, and `end_time`. The API rejects movies or screens from another cinema and overlapping shows on the same screen. Price requests contain a `prices` array with exactly one positive price for every seat category on the screen. Seats are not modified when show-specific prices change.

Example show request:

```json
{
  "movie": 12,
  "screen": 3,
  "show_date": "2026-10-20",
  "start_time": "14:00:00",
  "end_time": "16:00:00"
}
```

Example show price request:

```json
{
  "prices": [
    {"seat_type": "NORMAL", "price": "190.00"},
    {"seat_type": "GOLD", "price": "250.00"},
    {"seat_type": "PREMIUM", "price": "300.00"}
  ]
}
```

## 8. Automated checks

Automated API tests cover account registration, sign-in, cinema registration, movie access and validation, role-based visibility, create/update/delete access, and approval/rejection permissions.
