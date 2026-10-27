# Implemented Features

This document summarizes the implemented API behavior. See [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) for the complete setup sequence, request examples, and end-to-end workflow.

## Roles and authentication

- **Super Admin:** manages platform-level cinema administration, including approving and rejecting cinema registrations.
- **Tenant Admin:** manages the cinema they own.
- **User:** regular account; can view active show seat availability, make bookings, view their bookings, and cancel before a show starts.

Protected APIs use JWT access tokens:

```http
Authorization: Bearer <access_token>
```

Only Tenant Admins can use the current screen, seat, show, and show-price endpoints. This applies to reads as well as writes. Super Admins and regular Users are denied access.

## Accounts and cinemas

- `POST /api/auth/register/` creates a regular User account.
- `POST /api/cinemas/register/` creates a Tenant Admin and a Pending cinema together.
- `POST /api/auth/login/` returns access and refresh tokens with the user's role claim. Tenant Admins can sign in only after their assigned cinema is approved and Active; pending or rejected registrations receive a clear `401 Unauthorized` response.
- `POST /api/auth/refresh/` refreshes an access token.
- `POST /api/cinemas/{id}/approve/` and `/reject/` are Super Admin operations.
- Cinema list/detail and management permissions depend on the account role and cinema status.

## Movie catalogue

Movies are stored in the tenant cinema schema. The movie APIs support create, list, retrieve, update, and delete.

- A Tenant Admin can manage movies only for their own cinema.
- `POST /api/movies/` requires `X-Schema-Name`; the server verifies it matches the authenticated Tenant Admin's cinema.
- Movie `cinema` and `status` are read-only on create. Newly created movies start as `DRAFT`.
- A Tenant Admin may update a movie's status when appropriate. The show API currently checks cinema ownership, not whether the movie is `ACTIVE`.
- Regular Users see only Active movies for Active cinemas.
- Movie list behavior for Super Admins can use the schema header to select a cinema or omit it to list across cinemas.

The screen/show APIs do **not** use `X-Schema-Name`; they derive their tenant schema from the authenticated Tenant Admin.

## Screens, permanent layouts, shows, and prices

The workflow is sequential. Movie, screen, seat, show, and show-price data is tenant-local; the backend associates requests with the cinema owned by the authenticated Tenant Admin.

### 1. Create a screen

**`POST /api/shows/screens/`**

```json
{
  "name": "Screen 1",
  "total_seats": 150
}
```

The cinema is assigned by the server. Screen names must be unique within a cinema.

### 2. Configure the screen's permanent layout

**`POST /api/shows/screens/{screen_id}/configure-layout/`**

The request contains a `rows` array. Every row has `label`, `seat_count`, and `seat_type`; `gaps_after` is optional.

```json
{
  "rows": [
    {"label": "A", "seat_count": 15, "seat_type": "NORMAL", "gaps_after": [5, 10]},
    {"label": "B", "seat_count": 15, "seat_type": "GOLD"},
    {"label": "C", "seat_count": 15, "seat_type": "PREMIUM"},
    {"label": "D", "seat_count": 15, "seat_type": "RECLINER"}
  ]
}
```

That example defines 60 seats, so it is valid only for a screen whose capacity is 60. The sum of the row seat counts must equal `total_seats`; aisle gaps do not count as seats. Seat numbers are generated from the row label and ordinal (`A1`, `A2`, etc.). `gaps_after` inserts a positional gap after the specified seat without changing the seat count.

Supported seat types are `NORMAL`, `GOLD`, `PREMIUM`, and `RECLINER`. The API rejects duplicate row labels, duplicate generated seat numbers, invalid gap positions, and capacity mismatches. Layout configuration is one-time; another attempt returns `409 Conflict`. Screen capacity cannot be changed after seats are configured.

**`GET /api/shows/screens/{screen_id}/seats/`** retrieves the permanent seats and their categories.

### 3. Create a show

**`POST /api/shows/`**

```json
{
  "movie": 12,
  "screen": 3,
  "show_date": "2026-10-20",
  "start_time": "14:00:00",
  "end_time": "16:00:00"
}
```

The movie and screen must belong to the Tenant Admin's cinema. The screen must have a configured layout. The end time must follow the start time, and overlapping shows on the same screen and date are rejected.

**`GET /api/shows/`** lists the Tenant Admin's shows. **`GET /api/shows/{show_id}/`** retrieves one show.

### 4. Set or update prices for that show

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

Include exactly one positive price for each seat type present on the screen. The price set belongs to the show: another show on the same screen can use different prices. `PUT` replaces the full price set.

**`GET /api/shows/{show_id}/prices/`** retrieves the configured prices.

### 5. Customer show discovery and seat availability

Authenticated regular Users browse shows across active cinema schemas with **`GET /api/shows/`**. Optional query parameters are `date=YYYY-MM-DD`, `cinema_slug=<slug>`, and `movie_id=<id>`; the date defaults to today. Only upcoming shows at active cinemas and for active movies are returned, and a show must have a configured seat layout and a price for every seat category. Tenant Admins continue to use `GET /api/shows/` for their own cinema and `POST /api/shows/` to create shows; customers cannot create shows. `/api/shows/discover/` remains available as a customer-browsing alias.

**`GET /api/shows/{show_id}/seats/?cinema_slug=<slug>`** returns the screen's permanent seat records with the matching show price and live `status` (`AVAILABLE`, `HELD`, or `BOOKED`). The existing `is_available` boolean remains in the response and is true only for `AVAILABLE`. Customers must pass the cinema slug; the Tenant Admin uses the cinema derived from their JWT. Customer access is limited to active cinemas and active movies.

## Booking management

Only authenticated regular Users can hold, confirm, book, list, view, or cancel bookings. Customer requests select a cinema by its public `cinema_slug`; PostgreSQL schema names are never accepted from the customer.

| Method | Endpoint | Behavior |
|---|---|---|
| `POST` | `/api/bookings/holds/` | Hold selected seats for five minutes |
| `POST` | `/api/bookings/{booking_uuid}/confirm/` | Confirm an unexpired hold immediately, without payment |
| `POST` | `/api/bookings/` | Create an immediately confirmed booking (legacy flow) |
| `GET` | `/api/bookings/my/` | List the authenticated customer's bookings |
| `GET` | `/api/bookings/{booking_uuid}/` | Retrieve one of the customer's bookings |
| `POST` | `/api/bookings/{booking_uuid}/cancel/` | Cancel before show start; seats become available again |

Example create request:

```json
{
  "cinema_slug": "example-cinema",
  "show": 42,
  "seats": [101, 102]
}
```

The hold and immediate-booking APIs accept the same JSON request:

```json
{
  "cinema_slug": "example-cinema",
  "show": 42,
  "seats": [101, 102]
}
```

The API validates that the cinema and movie are active, the show has not started, and every selected seat belongs to the show's screen. It calculates the total from that show's `ShowSeatPrice` records; clients cannot submit prices. Each booking seat stores `price_at_booking`, preserving the charged price if show prices are later changed.

The booking transaction locks the show and selected seats, and a database uniqueness constraint prevents an active duplicate reservation for the same seat and show. Thus one physical seat can be booked for different showtimes, but not twice for the same show. A successful hold response includes a UUID booking ID, human-readable booking reference, `HELD` status, `hold_expires_at`, price snapshots, and total amount. Confirmation before the five-minute expiry changes its status to `CONFIRMED`. Confirming an expired hold returns `410 Gone`, marks it `EXPIRED`, and releases its seats; expired holds are also processed when customer show/seats/bookings are accessed.

Cancelled bookings remain in the customer's history and retain their price snapshots; their seats can be booked again. Cancellation is rejected after the show starts. The booking reference is the confirmation identifier; payment and downloadable ticket generation are not implemented.

## Tenant isolation and current limitations

- Cinema, account, and tenant registry data are in the shared `public` schema.
- Movie, screen, seat, show, and show-price rows are stored in the cinema's PostgreSQL schema.
- Screen, seat, show, and pricing views derive the cinema/schema from the authenticated Tenant Admin. The client cannot select a schema through a body field or header.
- Movie creation still uses the checked `X-Schema-Name` header described above.
- There is no individual seat update endpoint; the layout is intentionally immutable through the current API.
- Customer booking requests identify a cinema using its public slug, never its PostgreSQL schema name. Booking reads and operations locate tenant-local records without trusting a client-supplied schema.
- Booking seat availability is per show. An active seat can only be booked once for a particular show, while the same screen seat remains bookable for another show.
- Booking totals are calculated server-side from the selected show's category prices. Each booking seat stores a price snapshot so later price updates do not change past bookings.
- Cancellation before the show starts releases seats while retaining the cancelled booking and price history.
- Screens, movies, and cinemas that have booking history are protected from deletion; those delete requests return `409 Conflict`.
- Payment processing and downloadable ticket generation are not implemented. The booking reference is the confirmation identifier for now.

## Automated checks

The automated test suite covers authentication, cinema registration and access, movie permissions and validation, permanent seat-layout generation, screen capacity checks, show-specific prices, same-cinema validation, show overlap validation, customer show discovery and filtering, seat status, hold/expiry/confirmation, tenant schema selection, and Tenant Admin-only access.
