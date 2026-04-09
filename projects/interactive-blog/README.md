# Interactive Coffee/Tea Blog

A modern, high-performance, and interactive blog dedicated to the world of coffee and tea. Built with Next.js 14, Prisma, and Tailwind CSS.

## Features

- **Responsive Frontend**: Optimized for all devices using Tailwind CSS and Framer Motion.
- **Interactive Flavor Profiles**: Visual representations of beverage sensory profiles using morphing SVGs.
- **Live Search**: Fast, server-side search across posts, categories, and tags using PostgreSQL Full-Text Search.
- **Threaded Comments**: Efficiently managed comment trees with materialized paths and optimistic UI updates.
- **Media Management**: Structured metadata for all coffee and tea related assets.
- **Secure Authentication**: User authentication via NextAuth.js.

## Tech Stack

- **Framework**: [Next.js 14](https://nextjs.org/) (App Router)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/)
- **Database**: [PostgreSQL](https://www.postgresql.org/)
- **ORM**: [Prisma](https://www.prisma.io/)
- **Authentication**: [NextAuth.js](https://next-auth.js.org/)
- **Animations**: [Framer Motion](https://www.framer.com/motion/)
- **Validation**: [Zod](https://zod.dev/)

## Getting Started

### Prerequisites

- Node.js 18.x or later
- PostgreSQL database

### Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd interactive-blog
    ```

2.  **Install dependencies**:
    ```bash
    npm install
    ```

3.  **Set up environment variables**:
    Create a `.env` file in the root directory and add the following variables:
    ```env
    DATABASE_URL="postgresql://username:password@localhost:5432/interactive_blog"
    NEXTAUTH_SECRET="your-secret-key"
    NEXTAUTH_URL="http://localhost:3000"
    
    # Optional: Authentication Provider Keys (e.g., GitHub)
    # GITHUB_ID="your-github-id"
    # GITHUB_SECRET="your-github-secret"
    ```

4.  **Initialize the database**:
    ```bash
    npx prisma db push
    ```

5.  **Seed the database (optional)**:
    ```bash
    npm run prisma:seed
    ```
    *(Note: Ensure you have a seed script defined in `prisma/seed.ts`)*

6.  **Run the development server**:
    ```bash
    npm run dev
    ```
    Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

- `app/`: Next.js App Router routes and API endpoints.
- `components/`: Reusable React components.
- `lib/`: Shared libraries and utilities (Prisma client, Auth options).
- `prisma/`: Database schema and migrations.
- `public/`: Static assets (images, fonts).
- `styles/`: Global styles and Tailwind configuration.
- `tests/`: Unit and integration tests.

## Documentation

- [Technical Architecture](./architecture.md)
- [Interactivity Model](./interactivity.md)
- [Asset Inventory](./asset-inventory.md)
- [API Documentation](./docs/API.md)
- [Content Guide](./docs/CONTENT_GUIDE.md)
- [Deployment Runbook](./docs/DEPLOYMENT.md)

## Testing

Run the test suite using Jest:
```bash
npm test
```

## License

This project is licensed under the MIT License.
