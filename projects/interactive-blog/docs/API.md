# API Documentation

This document describes the available API endpoints for the Interactive Coffee/Tea Blog.

## Authentication

All API endpoints that require authentication use **NextAuth.js**.
To make authenticated requests, you must include a valid session cookie.

Roles:
- `ADMIN`: Full access to all resources.
- `AUTHOR`: Can create, update, and delete their own posts.
- `USER`: Regular viewer, can comment (if implemented).

---

## 1. Posts

### `GET /api/posts`
Fetches a list of blog posts.

- **Query Parameters**:
  - `status`: Optional. Filter by status (`DRAFT` or `PUBLISHED`).
- **Response**:
  - `200 OK`: Array of post objects with their category, author, and tags.
  - `400 Bad Request`: If an invalid status is provided.

### `POST /api/posts`
Creates a new blog post.

- **Authentication**: Required (`ADMIN` or `AUTHOR`).
- **Body**:
  ```json
  {
    "title": "Post Title",
    "slug": "post-slug",
    "content": "Post content in Markdown or HTML",
    "categoryId": "UUID of the category",
    "authorId": "UUID of the author",
    "featuredImage": "Optional. URL of the featured image",
    "status": "Optional. 'DRAFT' or 'PUBLISHED'. Default: 'DRAFT'"
  }
  ```
- **Response**:
  - `201 Created`: The created post object.
  - `401 Unauthorized`: If not authenticated or lack permissions.
  - `400 Bad Request`: If validation fails.

### `GET /api/posts/[id]`
Fetches a single post by ID or Slug.

- **Response**:
  - `200 OK`: Post object with detailed relations.
  - `404 Not Found`: If no post is found with the given ID or slug.

### `PATCH /api/posts/[id]`
Updates an existing post by ID.

- **Authentication**: Required (`ADMIN` or `AUTHOR`).
- **Body**: Same as `POST`, but all fields are optional.
- **Response**:
  - `200 OK`: The updated post object.
  - `401 Unauthorized`: If not authenticated or lack permissions.
  - `404 Not Found`: If the post doesn't exist.

### `DELETE /api/posts/[id]`
Deletes a post by ID.

- **Authentication**: Required (`ADMIN`).
- **Response**:
  - `204 No Content`: Successful deletion.
  - `401 Unauthorized`: If not authenticated or not an ADMIN.

---

## 2. Media Metadata

### `GET /api/media`
Fetches all media metadata.

- **Response**:
  - `200 OK`: Array of media metadata objects.

### `POST /api/media`
Creates or updates metadata for a media asset.

- **Authentication**: Required (`ADMIN`).
- **Body**:
  ```json
  {
    "assetId": "Unique ID of the asset (e.g., filename)",
    "altText": "Optional. Text for accessibility",
    "category": "Optional. Category of the asset",
    "dimensions": {
      "width": 1024,
      "height": 768
    }
  }
  ```
- **Response**:
  - `201 Created`: The upserted media metadata object.
  - `401 Unauthorized`: If not authenticated or not an ADMIN.

---

## 3. Search

### `GET /api/search`
Searches for published posts across title, content, categories, and tags.

- **Query Parameters**:
  - `q`: Required. The search query string.
- **Response**:
  - `200 OK`: Array of up to 5 matching post objects.
  - `400 Bad Request`: If query is missing.

---

## Asset Management Workflow

Media assets are managed through a combination of filesystem storage and database metadata.

1.  **Storage**: Assets are stored in the `/public/assets/` directory.
2.  **Referencing**: Assets should be referenced in posts using their relative URL path, e.g., `/assets/6119460_coffee_lichsu.png`.
3.  **Metadata**: To provide high-quality alt text and dimensions for SEO and accessibility:
    - Upload the image to `/public/assets/`.
    - Use the `POST /api/media` endpoint to register the asset's metadata with its `assetId` matching the filename.
4.  **Frontend Usage**: The blog uses the Next.js `Image` component which leverages this metadata for optimized rendering and layout stability.
