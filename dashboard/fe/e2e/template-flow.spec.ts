import { test, expect } from '@playwright/test';

test.describe('Template Picker Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/auth/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ username: 'test-user' }),
      }),
    );
    await page.route('**/api/home', (route) =>
      route.fulfill({ status: 404, body: '{}' }),
    );

    await page.goto('http://localhost:3001', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
  });

  test('home page renders greeting and command prompt', async ({ page }) => {
    const heading = page.getByRole('heading', { name: /what do you want to build/i });
    await expect(heading).toBeVisible({ timeout: 15000 });

    const textarea = page.locator('textarea[aria-label="Prompt"]');
    await expect(textarea).toBeVisible({ timeout: 5000 });
  });

  test('template picker tabs are visible and clickable', async ({ page }) => {
    const tabList = page.locator('[role="tablist"]');
    await expect(tabList).toBeVisible({ timeout: 15000 });

    const tabs = page.locator('[role="tab"]');
    expect(await tabs.count()).toBe(8);

    const firstTab = tabs.first();
    await expect(firstTab).toHaveAttribute('aria-selected', 'true');

    const secondTab = tabs.nth(1);
    await secondTab.click();
    await expect(secondTab).toHaveAttribute('aria-selected', 'true');
    await expect(firstTab).toHaveAttribute('aria-selected', 'false');
  });

  test('clicking a template shows @chip in prompt area, textarea stays empty', async ({ page }) => {
    const tabPanel = page.locator('[role="tabpanel"]');
    await expect(tabPanel).toBeVisible({ timeout: 15000 });

    // Click first template
    const firstRow = tabPanel.locator('button').first();
    await firstRow.click();

    // Wait for async load -- the @chip should appear inside the prompt form
    const chip = page.locator('text=/@.+/');
    await expect(chip.first()).toBeVisible({ timeout: 10000 });

    // The textarea should be EMPTY (template content not injected)
    const textarea = page.locator('textarea[aria-label="Prompt"]');
    const value = await textarea.inputValue();
    expect(value).toBe('');

    // Placeholder should change
    await expect(textarea).toHaveAttribute('placeholder', 'Add details about your project...');
  });

  test('user can type additional context alongside the @chip', async ({ page }) => {
    const tabPanel = page.locator('[role="tabpanel"]');
    await expect(tabPanel).toBeVisible({ timeout: 15000 });

    const firstRow = tabPanel.locator('button').first();
    await firstRow.click();

    // Wait for chip
    const chip = page.locator('text=/@.+/');
    await expect(chip.first()).toBeVisible({ timeout: 10000 });

    // Type additional context
    const textarea = page.locator('textarea[aria-label="Prompt"]');
    await textarea.fill('for a coffee delivery startup in NYC');

    // Both the chip and user text should coexist
    await expect(chip.first()).toBeVisible();
    expect(await textarea.inputValue()).toBe('for a coffee delivery startup in NYC');
  });

  test('removing the @chip clears the template attachment', async ({ page }) => {
    const tabPanel = page.locator('[role="tabpanel"]');
    await expect(tabPanel).toBeVisible({ timeout: 15000 });

    const firstRow = tabPanel.locator('button').first();
    await firstRow.click();

    // Wait for chip
    const chip = page.locator('text=/@.+/');
    await expect(chip.first()).toBeVisible({ timeout: 10000 });

    // Click the remove button on the chip
    const removeBtn = page.locator('[aria-label="Remove template"]');
    await removeBtn.click();

    // Chip should disappear
    await expect(chip.first()).not.toBeVisible({ timeout: 3000 });

    // Placeholder should revert
    const textarea = page.locator('textarea[aria-label="Prompt"]');
    await expect(textarea).toHaveAttribute('placeholder', 'What do you want to build?');
  });

  test('submit button is enabled with just a template (no text needed)', async ({ page }) => {
    const tabPanel = page.locator('[role="tabpanel"]');
    await expect(tabPanel).toBeVisible({ timeout: 15000 });

    const firstRow = tabPanel.locator('button').first();
    await firstRow.click();

    // Wait for chip
    const chip = page.locator('text=/@.+/');
    await expect(chip.first()).toBeVisible({ timeout: 10000 });

    // Submit button should be enabled even without text
    const submitBtn = page.locator('button[aria-label="Send prompt (Ctrl or Cmd + Enter)"]');
    await expect(submitBtn).toBeEnabled();
  });

  test('keyboard navigation works on template tabs', async ({ page }) => {
    const tabList = page.locator('[role="tablist"]');
    await expect(tabList).toBeVisible({ timeout: 15000 });

    const tabs = page.locator('[role="tab"]');
    await tabs.first().focus();

    await page.keyboard.press('ArrowRight');
    await expect(tabs.nth(1)).toHaveAttribute('aria-selected', 'true');

    await page.keyboard.press('ArrowLeft');
    await expect(tabs.first()).toHaveAttribute('aria-selected', 'true');
  });

  test('field count badges are displayed for each template', async ({ page }) => {
    const tabPanel = page.locator('[role="tabpanel"]');
    await expect(tabPanel).toBeVisible({ timeout: 15000 });

    const badges = page.locator('text=/\\d+ fields/');
    expect(await badges.count()).toBeGreaterThan(0);
  });
});
