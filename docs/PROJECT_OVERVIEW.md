# Cinema Booking Project — Simple Overview

## What this project is

This project is the foundation of a cinema booking system. It currently provides APIs for user accounts, sign-in, cinema registration and management, cinema approval, and cinema movie catalogues.

**Important:** Showtimes, seat selection, ticket booking, and payments are not implemented yet. Those would be later features.

## Who can use it

- **Super Admin** looks after the whole platform. They can manage cinemas and approve or reject registrations.
- **Tenant Admin** is the manager of one cinema. They can view and update their own cinema.
- **User** is a cinema customer. They can view active cinemas.

## How the current system works

1. A person can sign up as a regular user, or a cinema owner can register their cinema and owner account together.
2. The cinema registration is saved with **Pending** status.
3. A Super Admin reviews it and approves or rejects it.
4. Once approved, the cinema becomes **Active** and regular users can see it.
5. A tenant admin can update details for their own cinema. A Super Admin can manage any cinema.
6. Sign-in returns access and refresh tokens. The access token is sent with protected API requests to identify the user and their role.

## Features implemented so far

### Accounts and access

- Three account roles: Super Admin, Tenant Admin, and User.
- Regular account registration creates a User account.
- Tenant Admin account registration is restricted to a Super Admin.
- Sign-in, access-token refresh, sign-out, and a "who am I" account endpoint.
- Super Admin-only access to another user's account details.
- Role-specific test endpoints for checking access.

### Cinema management

- Cinema registration creates a Tenant Admin account and a Pending cinema.
- Cinema records include name, domain, slug, schema name, owner, status, address, city, and contact details.
- List and detail APIs show cinemas according to the signed-in user's role.
- Cinema details can be updated by a Super Admin or the cinema's own Tenant Admin.
- Only a Super Admin can delete a cinema or approve/reject it.
- Only Active cinemas are visible to regular users.

### Movie catalogue

- Each movie is stored in its cinema's PostgreSQL schema and linked to that cinema.
- Movies include title, description, duration in minutes, language, genre, release date, and Draft/Active/Inactive status.
- New movies always start as Draft. A Tenant Admin can later change the status to Active or Inactive.
- Tenant Admins can create, update, and delete movies only for their own cinema.
- Super Admins can view all movies but cannot create, update, or delete them.
- Regular users can view Active movies only when their cinema is Active.
- Movie IDs are allocated across cinemas so the existing `/api/movies/{id}/` routes can identify a movie. If duplicate IDs are encountered across schemas, the detail API responds with `409 Conflict`.

### Automated checks

Automated API tests check account registration and authentication, cinema registration, role-based access, cinema changes, movie access and validation, deletion, and approval/rejection.

## API map

Protected APIs require this request header:

```text
Authorization: Bearer <access_token>
```

### Account APIs

The account API prefix is `/api/auth/`.

| Action | Method and path | Access |
|---|---|---|
| Register a regular user | `POST /api/auth/register/` | Anyone |
| Register a Tenant Admin | `POST /api/auth/register/tenant/` | Super Admin |
| Sign in and get tokens | `POST /api/auth/login/` | Anyone with an account |
| Refresh an access token | `POST /api/auth/refresh/` | Anyone with a valid refresh token |
| Sign out using a refresh token | `POST /api/auth/logout/` | Anyone with a valid refresh token |
| View your own account | `GET /api/auth/me/` | Signed-in user |
| View a user's account | `GET /api/auth/{user_id}/` | Super Admin |

### Cinema APIs

The cinema API prefix is `/api/cinemas/`.

| Action | Method and path | Access |
|---|---|---|
| Register a cinema and its owner | `POST /api/cinemas/register/` | Anyone |
| List cinemas | `GET /api/cinemas/` | Signed-in user; results depend on role |
| Create a cinema through the management API | `POST /api/cinemas/` | Super Admin |
| View a cinema | `GET /api/cinemas/{id}/` | Super Admin, its Tenant Admin, or a User if Active |
| Update a cinema | `PUT` or `PATCH /api/cinemas/{id}/` | Super Admin or its Tenant Admin |
| Delete a cinema | `DELETE /api/cinemas/{id}/` | Super Admin |
| Approve a cinema | `POST /api/cinemas/{id}/approve/` | Super Admin |
| Reject a cinema | `POST /api/cinemas/{id}/reject/` | Super Admin |

### Movie APIs

The movie API prefix is `/api/movies/`. For movie registration, the Tenant Admin sends their own cinema's schema in the `X-Schema-Name` request header. The server checks that this schema belongs to the signed-in Tenant Admin, then stores the movie in it. The same header can be used with `GET /api/movies/` to select one cinema's movie list. A Tenant Admin can select only their own schema; a Super Admin can select any cinema's schema. Without the header, a Tenant Admin sees their own cinema's movies and a Super Admin sees movies across cinemas. The JSON body contains movie details such as `title`, `duration`, `language`, `genre`, and `release_date`; the cinema is selected by the checked header, not by a client-supplied cinema ID.

| Action | Method and path | Access |
|---|---|---|
| Create a movie | `POST /api/movies/` | Tenant Admin for their own cinema |
| List movies | `GET /api/movies/` | Signed-in user; results depend on role |
| View a movie | `GET /api/movies/{id}/` | Super Admin, its Tenant Admin, or a User if the movie and cinema are Active |
| Update a movie | `PUT` or `PATCH /api/movies/{id}/` | Its Tenant Admin |
| Delete a movie | `DELETE /api/movies/{id}/` | Its Tenant Admin |

## Main project folders

- `authentication/` contains user roles, account APIs, permissions, and authentication tests.
- `cinema/` contains the cinema record, cinema APIs, permissions, approval actions, and cinema tests.
- `movies/` contains cinema movie records, movie APIs, permissions, admin setup, and movie tests.
- `config/` contains the Django project settings and the main URL routing.
- `docs/` contains the project notes and implementation record.

## What could be added next

The project currently handles the cinema setup, movie catalogue, and access-control foundation. Possible next steps are adding cinema screens, showtimes, seats, bookings, ticket confirmation, and payment handling.

See [IMPLEMENTED_FEATURES.md](./IMPLEMENTED_FEATURES.md) for a shorter, step-by-step record of the features implemented.
