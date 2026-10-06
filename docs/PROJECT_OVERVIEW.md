# Cinema Booking Project — Simple Overview

## What this project is

This project is the beginning of a cinema booking system. It currently provides APIs for user accounts, sign-in, cinema registration, cinema management, and cinema approval.

**Important:** Movie listings, showtimes, seat selection, ticket booking, and payments are not implemented yet. Those would be later features.

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

### Automated checks

Automated API tests check account registration and authentication, cinema registration, role-based access, cinema changes, deletion, and approval/rejection. The authentication and cinema test suites passed together with 15 tests in the last recorded run.

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

## Main project folders

- `authentication/` contains user roles, account APIs, permissions, and authentication tests.
- `cinema/` contains the cinema record, cinema APIs, permissions, approval actions, and cinema tests.
- `config/` contains the Django project settings and the main URL routing.
- `docs/` contains the project notes and implementation record.

## What could be added next

The project currently handles the cinema setup and access-control foundation. Possible next steps are adding movies, cinema screens, showtimes, seats, bookings, ticket confirmation, and payment handling.

See [IMPLEMENTED_FEATURES.md](./IMPLEMENTED_FEATURES.md) for a shorter, step-by-step record of the features implemented.
