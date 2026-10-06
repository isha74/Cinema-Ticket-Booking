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

Automated API tests cover account registration, sign-in, cinema registration, role-based visibility, create/update/delete access, and approval/rejection permissions. The authentication and cinema API test suites passed together with **15 tests**.
