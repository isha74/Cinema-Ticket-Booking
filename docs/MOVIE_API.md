# Movie API

## Register a movie

`POST /api/movies/` requires a tenant-admin access token and the cinema schema header. Use `multipart/form-data` when uploading a poster image; this is a file upload, not a JSON string or base64 field.

### Headers

```http
Authorization: Bearer <access_token>
X-Schema-Name: <your_cinema_schema_name>
Content-Type: multipart/form-data
```

### Fields

| Field | Required | Format |
| --- | --- | --- |
| `title` | Yes | Text |
| `description` | No | Text |
| `duration` | Yes | Integer minutes, 1–32767 |
| `language` | Yes | Text |
| `genre` | Yes | Text |
| `release_date` | Yes | `YYYY-MM-DD` |
| `poster` | No | Image file (JPEG, PNG, or another image format supported by Pillow), maximum 10 MB |

`cinema`, `cinema_name`, `id`, `created_at`, and `status` are not supplied on registration. The cinema is assigned from the authenticated tenant and the schema header; new movies start as `DRAFT`.

### Full cURL example

```bash
curl -X POST "http://localhost:8000/api/movies/" \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Schema-Name: <your_cinema_schema_name>" \
  -F "title=The Last Voyage" \
  -F "description=A short movie description." \
  -F "duration=126" \
  -F "language=English" \
  -F "genre=Drama" \
  -F "release_date=2026-10-24" \
  -F "poster=@/path/to/the-last-voyage-poster.jpg;type=image/jpeg"
```

With `curl -F`, do not manually set the `Content-Type` header: curl supplies the multipart boundary. In Postman, choose **Body → form-data**, set the listed values as text, set `poster` to **File**, and provide the two headers.

The response includes a `poster` URL when an image was uploaded, or `null` when omitted. During development, uploaded files are served from `/media/`. In production, configure the web server or object storage to serve the configured Django media storage.

## Update a movie poster

Send `PATCH /api/movies/<movie_id>/` with the same authorization and cinema schema headers. Use multipart form data and include `poster` as a file to replace it. The existing field can be cleared with an empty value/null where supported by the client serializer.
