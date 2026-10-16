# Cinema Booking Project

## Overview

This project provides APIs for account authentication, cinema registration and approval, cinema-specific movie catalogues, permanent screen seat layouts, show scheduling, and show-specific seat-category pricing.

Seat layout is configured once for a screen. Shows refer to that screen and have their own category prices, so the same seat can have different prices at different showtimes.

Customer seat booking, booking history, cancellation, and ticket-reference generation are implemented. Customer-facing cinema/movie/show discovery, payment processing, and downloadable ticket issuance are not implemented yet.

## Roles

- **Super Admin:** approves or rejects cinema registrations and manages platform-level cinema administration.
- **Tenant Admin:** manages the cinema they own. Only Tenant Admins can use screen, seat-layout, show, and show-price APIs.
- **User:** regular customer account. Can view active show seat availability and manage their own bookings; customer-facing cinema/movie/show discovery is not implemented yet.

Protected endpoints require a JWT access token:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

For screen, layout, show, and pricing requests, the backend finds the Tenant Admin's cinema from the authenticated user and sets the PostgreSQL tenant schema itself. **Do not send a schema name, cinema ID, or cinema ID override for these operations.** Sending an `X-Schema-Name` header does not switch the tenant for these endpoints.

Movie creation is an existing exception: `POST /api/movies/` currently requires the tenant's `X-Schema-Name` header. The API checks that it matches the authenticated Tenant Admin's cinema before saving.

## End-to-end operations flow

### 1. Register a cinema and Tenant Admin

**`POST /api/cinemas/register/`** — public.

Example:

```json
{
  "username": "cinema_owner",
  "email": "owner@example.com",
  "password": "<password>",
  "name": "Example Cinema",
  "domain": "example.com",
  "address": "1 Main Street",
  "city": "Example City",
  "contact_email": "contact@example.com",
  "contact_phone": "+1-555-0100"
}
```

The API creates the Tenant Admin and the cinema, generates its slug and PostgreSQL schema name, and initially marks the cinema **Pending**.

### 2. Approve the cinema

A Super Admin approves the registration:

**`POST /api/cinemas/{cinema_id}/approve/`**

Rejected cinemas remain unavailable for normal active-cinema browsing. The Tenant Admin should sign in after registration/approval using the account created for the cinema.

### 3. Sign in as the Tenant Admin

**`POST /api/auth/login/`**

```json
{
  "username": "cinema_owner",
  "password": "<password>"
}
```

Use the returned `access` token as the Bearer token for the remaining Tenant Admin operations. Send `refresh` to `/api/auth/refresh/` when the access token expires.

### 4. Register a movie

**`POST /api/movies/`**

Include `X-Schema-Name` with the `schema_name` returned in the cinema registration response. For this movie endpoint, the backend verifies that it belongs to the authenticated Tenant Admin.

```http
X-Schema-Name: <tenant_schema_name>
```

```json
{
  "title": "Example Film",
  "description": "A short description.",
  "duration": 120,
  "language": "English",
  "genre": "Drama",
  "release_date": "2026-10-20"
}
```

New movies are created with **Draft** status. A Tenant Admin can change the status to `ACTIVE` when appropriate. The current show API verifies that the movie belongs to the same cinema but does not require it to be `ACTIVE`. Keep the `id` returned by the API; that movie ID is used when creating a show.

### 5. Create a screen

**`POST /api/shows/screens/`**

```json
{
  "name": "Screen 1",
  "total_seats": 150
}
```

The Tenant Admin's cinema is assigned by the server. The screen and seats live in that cinema's PostgreSQL schema. Save the returned screen `id`.

Other screen endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/shows/screens/` | List screens belonging to the authenticated Tenant Admin's cinema |
| `GET` | `/api/shows/screens/{screen_id}/` | Retrieve a screen |
| `PUT` / `PATCH` | `/api/shows/screens/{screen_id}/` | Update screen details; capacity cannot change after layout generation |
| `DELETE` | `/api/shows/screens/{screen_id}/` | Delete a screen |

### 6. Configure the permanent seat layout

**`POST /api/shows/screens/{screen_id}/configure-layout/`**

```json
{
  "rows": [
    {
      "label": "A",
      "seat_count": 15,
      "seat_type": "NORMAL",
      "gaps_after": [5, 10]
    },
    {
      "label": "B",
      "seat_count": 15,
      "seat_type": "GOLD"
    },
    {
      "label": "C",
      "seat_count": 15,
      "seat_type": "GOLD"
    },
    {
      "label": "D",
      "seat_count": 15,
      "seat_type": "GOLD"
    },
    {
      "label": "E",
      "seat_count": 15,
      "seat_type": "PREMIUM"
    },
    {
      "label": "F",
      "seat_count": 15,
      "seat_type": "PREMIUM"
    },
    {
      "label": "G",
      "seat_count": 15,
      "seat_type": "PREMIUM"
    },
    {
      "label": "H",
      "seat_count": 15,
      "seat_type": "PREMIUM"
    },
    {
      "label": "I",
      "seat_count": 15,
      "seat_type": "RECLINER"
    },
    {
      "label": "J",
      "seat_count": 15,
      "seat_type": "RECLINER"
    }
  ]
}
```

This example creates **150 seats** for a screen whose capacity is 150. Replace the rows and seat counts to match the actual screen. The sum of all `seat_count` values must equal `total_seats`; aisle gaps do not count as seats.

Supported seat types are `NORMAL`, `GOLD`, `PREMIUM`, and `RECLINER`. `gaps_after` contains seat numbers after which the visual position should leave a gap, for example `[5, 10]`. Seats are generated with row labels and seat numbers such as `A1`, `A2`, and `B1`.

The API rejects duplicate row labels, generated duplicate seat numbers, invalid gaps, unsupported seat types, and a seat count that differs from screen capacity. A configured layout is permanent: a second layout configuration request returns `409 Conflict`. Screen capacity cannot be changed after seats have been generated. Do not delete or reconfigure seats after bookings are introduced without adding a controlled migration process.

To retrieve the permanent seats:

**`GET /api/shows/screens/{screen_id}/seats/`**

### 7. Create a show

**`POST /api/shows/`**

Use the movie ID from step 4 and the screen ID from step 5:

```json
{
  "movie": 12,
  "screen": 3,
  "show_date": "2026-10-20",
  "start_time": "14:00:00",
  "end_time": "16:00:00"
}
```

The movie and screen must belong to the authenticated Tenant Admin's cinema, and the screen must already have a seat layout. The end time must be later than the start time. Shows that overlap on the same screen and date are rejected. Save the returned show `id`.

Other show endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/shows/` | List shows for the authenticated Tenant Admin's cinema |
| `GET` | `/api/shows/{show_id}/` | Retrieve a show |

### 8. Set prices for that show

**`PUT /api/shows/{show_id}/prices/`**

```json
{
  "prices": [
    {"seat_type": "NORMAL", "price": "190.00"},
    {"seat_type": "GOLD", "price": "250.00"},
    {"seat_type": "PREMIUM", "price": "300.00"},
    {"seat_type": "RECLINER", "price": "575.00"}
  ]
}
```

Provide exactly one positive price for every seat type present in this screen's layout; do not include unused types. Prices are saved against this show, not the screen. For example, an afternoon show can price `NORMAL` at `150.00` and an evening show on the same screen can price it at `190.00` without changing any seats.

**`GET /api/shows/{show_id}/prices/`** retrieves the prices configured for one show. `PUT` replaces that show's complete price set.

### 9. Retrieve the seats and prices for a show

**`GET /api/shows/{show_id}/seats/`**

For a customer, pass the cinema slug as a query parameter. The API returns the screen's permanent seats with the price for each seat's category in that particular show and an `is_available` flag. The Tenant Admin may call this endpoint using their own cinema from their JWT without the slug.

```http
GET /api/shows/42/seats/?cinema_slug=example-cinema
```

Example response item:

```json
{
  "id": 1,
  "screen": 3,
  "row": "A",
  "seat_number": "A1",
  "position": 1,
  "seat_type": "NORMAL",
  "price": "190.00",
  "is_available": true
}
```

### 10. Book selected seats

Only a regular authenticated customer can book. The cinema slug identifies the tenant; clients never send a PostgreSQL schema name. Send the show ID and selected seat IDs returned by the availability endpoint:

**`POST /api/bookings/`**

```json
{
  "cinema_slug": "example-cinema",
  "show": 42,
  "seats": [101, 102]
}
```

The server verifies that the cinema and movie are active, the show has not started, all selected seats belong to its screen, and all selected seat categories have a configured show price. It calculates the total itself and stores each seat's price at booking time. The database and transaction prevent a seat from being active in two bookings for the same show. A seat may still be booked for a different show.

A successful response includes the booking UUID, `booking_reference`, confirmed status, selected seats, and total. The booking reference is the current ticket/confirmation identifier; PDF/e-ticket generation and payment are not part of this implementation.

### 11. View and cancel bookings

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/bookings/my/` | List the authenticated customer's bookings across cinemas |
| `GET` | `/api/bookings/{booking_uuid}/` | Retrieve one of the customer's bookings |
| `POST` | `/api/bookings/{booking_uuid}/cancel/` | Cancel before the show starts and release its seats |

Cancelled bookings and their price snapshots remain in history; their seats become available again for that show. A customer cannot view or cancel another customer's booking. Screens, movies, and cinemas with booking history cannot be deleted; the API returns `409 Conflict` to preserve booking records.

## API access summary

| Operation | Endpoint | Who can use it |
|---|---|---|
| Register regular account | `POST /api/auth/register/` | Anyone |
| Register cinema and owner | `POST /api/cinemas/register/` | Anyone |
| Approve or reject cinema | `POST /api/cinemas/{id}/approve/` or `/reject/` | Super Admin |
| Create, update, delete movies | `/api/movies/` | Tenant Admin for their own cinema |
| Create/manage screens and layouts | `/api/shows/screens/...` | Tenant Admin only |
| Create shows and configure prices | `/api/shows/...` | Tenant Admin only |
| View show seat availability | `GET /api/shows/{id}/seats/` | Tenant Admin for own cinema; authenticated User with `cinema_slug` |
| Create/view/cancel bookings | `/api/bookings/...` | Authenticated regular User only |
| Payment and downloadable tickets | Not implemented | Not available yet |

Super Admins are not allowed to use screen, seat, show, show-price, or booking APIs. Customer show discovery still needs a dedicated API.

## Data and tenant-schema behavior

- Cinema ownership and account records are stored in the shared `public` schema.
- Movie, screen, seat, show, and show-price data are stored in each cinema's PostgreSQL schema.
- For screen/show APIs, the backend derives the schema from the authenticated Tenant Admin's cinema record. The client must not choose a tenant schema.
- Movie creation is an existing legacy exception and currently needs a checked `X-Schema-Name` header.
- `python manage.py migrate` applies the Django migration history. Tenant schemas are created/provisioned by the existing tenant and app initialization logic.

## Current limitations and next feature

Customer-facing cinema/movie/show discovery, payment processing, and downloadable ticket generation remain future work. The client must never set ticket prices; booking totals and price snapshots are calculated from the selected show's configured `ShowSeatPrice` values.
