# Content Guide

This guide describes how to add new beverage-related content and interactive modules to the blog.

## 1. Adding a New Blog Post

### Via API
You can add a new post by sending a `POST` request to `/api/posts`.

### Manual Addition (Development)
If you're developing locally and want to add posts without using an API client, you can:
1.  **Direct Database Update**: Use Prisma Studio (`npx prisma studio`) to add records directly to the `Post` table.
2.  **Seeding**: Add your new content to `prisma/seed.ts` and run `npm run prisma:seed`.

### Post Content Formatting
The `content` field supports Markdown or HTML (depending on your renderer implementation). It is recommended to use standard Markdown for consistency.

---

## 2. Using Interactive Flavor Profiles

The `FlavorProfile` component provides a visual, animated representation of a beverage's sensory profile.

### Component Usage
To use the `FlavorProfile` component in a page or another component:

```tsx
import FlavorProfile from '@/components/blog/FlavorProfile';

export default function MyPostPage() {
  return (
    <FlavorProfile 
      sweetness={0.8} 
      acidity={0.4} 
      body={0.7} 
      bitterness={0.2} 
      label="Ethiopian Yirgacheffe Profile"
    />
  );
}
```

### Attributes (0.0 to 1.0)
- **Sweetness**: Affects the top-vertical point of the SVG blob.
- **Acidity**: Affects the right-horizontal point.
- **Body**: Affects the bottom-vertical point.
- **Bitterness**: Affects the left-horizontal point.

The component uses **Framer Motion** for smooth spring-based transitions when values change.

---

## 3. Adding New Interactive Modules

If you want to create a new interactive module (e.g., a "Brew Timer" or "Coffee Calculator"):

1.  **Create the Component**: Add a new `.tsx` file in `components/interactive/`.
2.  **Use Client Directive**: Since these modules are interactive, ensure they are client components by adding `"use client";` at the top.
3.  **Incorporate Animations**: Use **Framer Motion** to ensure the interactive experience is smooth and high-quality.
4.  **Theming**: Use the project's Tailwind color palette (e.g., `text-coffee-dark`, `bg-coffee-light`) to maintain consistency.

---

## 4. Managing Categories and Tags

Categories and tags are essential for organizing brews and improving searchability.

- **Categories**: Each post belongs to one Category (e.g., "Pour Over", "Espresso", "Herbal Tea").
- **Tags**: Posts can have multiple Tags for more granular classification (e.g., "Single Origin", "Caffeine-Free", "Light Roast").

To add new ones, use Prisma Studio or the relevant API endpoints if they are implemented.
