# Deployment Runbook

This guide describes how to deploy the Interactive Coffee/Tea Blog to a production environment.

## 1. Production Requirements

- Node.js 18.x+
- Managed PostgreSQL (e.g., Neon, Vercel Postgres, AWS RDS)
- Environment Variables management (e.g., Vercel Dashboard, `.env.production`)

---

## 2. Environment Variables (Production)

Ensure these variables are set in your production environment:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | Postgres connection string | `postgresql://user:pass@ep-flat-fog-12345.us-east-2.aws.neon.tech/blog` |
| `NEXTAUTH_SECRET` | Secret for Auth.js | `openssl rand -base64 32` |
| `NEXTAUTH_URL` | Production URL | `https://your-blog-domain.com` |
| `GITHUB_ID` | OAuth Client ID (optional) | `Ov23li...` |
| `GITHUB_SECRET` | OAuth Client Secret (optional) | `7f4e8b...` |

---

## 3. Step-by-Step Deployment (Vercel)

The easiest way to deploy this Next.js project is via **Vercel**.

1.  **Link Repository**: Import your GitHub repo in the Vercel Dashboard.
2.  **Add Env Vars**: Add all production variables listed above.
3.  **Deploy**: Vercel will automatically detect the Next.js project and build it.
4.  **Database Migration**:
    - During the build phase, Vercel will run `npx prisma generate`.
    - To sync the schema with your production database, run:
      ```bash
      npx prisma db push --force-reset
      ```
      *Warning: Be careful when using --force-reset on existing production data.*

---

## 4. Manual Deployment (VPS/Server)

1.  **Install dependencies**:
    ```bash
    npm ci
    ```
2.  **Generate Prisma Client**:
    ```bash
    npx prisma generate
    ```
3.  **Build the project**:
    ```bash
    npm run build
    ```
4.  **Start the server**:
    ```bash
    npm start
    ```
    You may want to use a process manager like **PM2** to keep the server running.

---

## 5. Post-Deployment Checklist

- [ ] Verify that all environment variables are correctly set.
- [ ] Check if the database connection is established.
- [ ] Test the authentication flow (GitHub/Google login).
- [ ] Verify search functionality (ensure Postgres FTS is working).
- [ ] Check if media assets are loading correctly (optimized via Next.js).
- [ ] Run production tests if applicable.
