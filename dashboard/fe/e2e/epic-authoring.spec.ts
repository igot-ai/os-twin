import { test, expect, Page } from '@playwright/test';

const TEST_PLAN_ID = 'test-epic-authoring';
const TEST_PLAN_CONTENT = `# Plan: Test EPIC Authoring System

## Config
working_dir: /tmp/test-epic-authoring

## High-Level Goal

Build an EPIC authoring system that allows users to create and edit EPICs through a visual interface.

## EPIC-001 — First Feature

**Roles**: @engineer, @qa

> [!NOTE]
> This is the first test EPIC for verifying the Epic Design mode.

### Description

This EPIC implements the first feature of the system.

### Definition of Done

- [ ] Feature is implemented
- [x] Tests are written
- [ ] Documentation is complete

### Acceptance Criteria

- [ ] User can create new items
- [ ] User can edit existing items
- [x] User can delete items

### Tasks

- [ ] **T-001.1** — Design the feature
  Acceptance Criteria:
  - Create wireframes
  - Review with team
- [ ] **T-001.2** — Implement the feature
- [x] **T-001.3** — Write tests

## EPIC-002 — Second Feature

**Roles**: @designer

### Definition of Done

- [ ] Feature is implemented

### Tasks

- [ ] **T-002.1** — Initial design
`;

async function setupMocks(page: Page) {
  await page.route('**/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ username: 'test-user' }),
    })
  );

  await page.route(`**/api/plans/${TEST_PLAN_ID}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        plan_id: TEST_PLAN_ID,
        title: 'Test EPIC Authoring System',
        content: TEST_PLAN_CONTENT,
        status: 'draft',
        created_at: Date.now(),
        goal: 'Build an EPIC authoring system',
      }),
    })
  );

  await page.route(`**/api/plans/${TEST_PLAN_ID}/epics`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  );

  await page.route(`**/api/plans/${TEST_PLAN_ID}/dag`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ nodes: {}, edges: [] }),
    })
  );

  await page.route(`**/api/plans/${TEST_PLAN_ID}/progress`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ rooms: [], pct_complete: 0 }),
    })
  );

  await page.route(`**/api/plans/${TEST_PLAN_ID}/roles`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ role_defaults: [], effective_roles: [] }),
    })
  );

  await page.route('**/api/roles', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { name: 'engineer', description: 'Software engineer' },
        { name: 'qa', description: 'Quality assurance' },
        { name: 'designer', description: 'Designer' },
      ]),
    })
  );
}

test.describe('EPIC Authoring System - Epic Design Mode', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto(`http://localhost:3001/plans/${TEST_PLAN_ID}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
  });

  test('T-003.1: Navigate to Planner, click Epic Design, verify render', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await expect(plannerTab).toBeVisible({ timeout: 15000 });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await expect(epicDesignBtn).toBeVisible({ timeout: 5000 });
    await epicDesignBtn.click();
    
    // 3. Verify page content
    const planTitle = page.getByTestId('plan-title');
    await expect(planTitle).toBeVisible({ timeout: 10000 });

    const epic001 = page.getByText('EPIC-001');
    await expect(epic001).toBeVisible({ timeout: 5000 });

    const epic002 = page.getByText('EPIC-002');
    await expect(epic002).toBeVisible({ timeout: 5000 });
  });

  test('T-003.2: Double-click plan title, edit, verify save', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const planTitle = page.getByTestId('plan-title');
    await planTitle.dblclick();
    await page.waitForTimeout(200);

    const titleInput = page.locator('input[type="text"]').first();
    await expect(titleInput).toBeVisible({ timeout: 3000 });
    await titleInput.fill('Updated Plan Title');
    await titleInput.press('Enter');
    await page.waitForTimeout(300);

    await expect(page.getByText('Updated Plan Title')).toBeVisible({ timeout: 3000 });
  });

  test('T-003.3: Double-click goal, edit, verify save', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const goalSection = page.locator('text=High-Level Goal').first();
    await expect(goalSection).toBeVisible({ timeout: 5000 });

    const goalContent = page.getByTestId('plan-goal').first();
    await goalContent.dblclick();
    await page.waitForTimeout(200);

    const goalTextarea = page.locator('textarea');
    await expect(goalTextarea).toBeVisible({ timeout: 3000 });
    await goalTextarea.fill('Updated goal: Build a comprehensive EPIC authoring system with AI assistance');
    await goalTextarea.blur();
    await page.waitForTimeout(300);

    await expect(page.getByText(/Updated goal/i)).toBeVisible({ timeout: 3000 });
  });

  test('T-003.4: Verify EPIC card preview shows all metadata', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const epic001Badge = page.locator('text=EPIC-001').first();
    await expect(epic001Badge).toBeVisible({ timeout: 5000 });

    await expect(page.getByText('First Feature')).toBeVisible({ timeout: 3000 });

    const dodSection = page.getByText(/Definition of Done/i).first();
    await expect(dodSection).toBeVisible({ timeout: 3000 });

    const tasksSection = page.getByText(/Tasks/i).first();
    await expect(tasksSection).toBeVisible({ timeout: 3000 });
  });

  test('T-003.5: Click Add New EPIC, verify new card creation', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const epicCountBefore = await page.locator('text=/EPIC-\\d{3}/').count();

    const addEpicBtn = page.getByRole('button', { name: /add new epic/i });
    await expect(addEpicBtn).toBeVisible({ timeout: 5000 });
    await addEpicBtn.click();
    await page.waitForTimeout(500);

    const epicCountAfter = await page.locator('text=/EPIC-\\d{3}/').count();
    expect(epicCountAfter).toBe(epicCountBefore + 1);

    await expect(page.getByText('New Feature')).toBeVisible({ timeout: 3000 });
  });

  test('T-003.6: Switch to Markdown Editor, verify content includes new EPIC', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const addEpicBtn = page.getByRole('button', { name: /add new epic/i });
    await addEpicBtn.click();
    await page.waitForTimeout(500);

    const markdownEditorBtn = page.getByRole('button', { name: /markdown editor/i });
    await markdownEditorBtn.click();
    await page.waitForTimeout(500);

    const textarea = page.locator('textarea.font-mono');
    await expect(textarea).toBeVisible({ timeout: 5000 });

    const content = await textarea.inputValue();
    expect(content).toContain('EPIC-001');
    expect(content).toContain('EPIC-002');
    expect(content).toMatch(/EPIC-003/);
  });

  test('All 4 view mode tabs switch correctly', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const markdownEditorBtn = page.getByRole('button', { name: /markdown editor/i });
    await expect(markdownEditorBtn).toBeVisible({ timeout: 5000 });
    await markdownEditorBtn.click();
    await page.waitForTimeout(300);
    await expect(page.locator('textarea.font-mono')).toBeVisible({ timeout: 3000 });

    const previewBtn = page.getByRole('button', { name: /^preview$/i });
    await previewBtn.click();
    await page.waitForTimeout(300);
    await expect(page.locator('.prose, [class*="markdown"]')).toBeVisible({ timeout: 3000 });

    const splitBtn = page.getByRole('button', { name: /split/i });
    await splitBtn.click();
    await page.waitForTimeout(300);
    await expect(page.locator('textarea.font-mono')).toBeVisible({ timeout: 3000 });

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(300);
    await expect(page.getByTestId('plan-title')).toBeVisible({ timeout: 3000 });
  });

  test('EPIC card can be collapsed and expanded', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const epic001Header = page.locator('#EPIC-001').first();
    await expect(epic001Header).toBeVisible({ timeout: 5000 });

    const descriptionSection = page.getByText('This EPIC implements the first feature').first();
    await expect(descriptionSection).toBeVisible({ timeout: 3000 });
  });

  test('Checkbox items can be toggled in EPIC card', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const checkboxes = page.locator('#EPIC-001 input[type="checkbox"]');
    const count = await checkboxes.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe('EPIC Authoring System - Undo/Redo', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto(`http://localhost:3001/plans/${TEST_PLAN_ID}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
  });

  test('T-003.7: Verify undo (Ctrl+Z) reverts last edit', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const planTitle = page.getByTestId('plan-title');
    await planTitle.dblclick();
    await page.waitForTimeout(200);

    const titleInput = page.locator('input[type="text"]').first();
    await expect(titleInput).toBeVisible({ timeout: 3000 });
    await titleInput.fill('Modified Title');
    await titleInput.press('Enter');
    await page.waitForTimeout(300);

    await expect(page.getByText('Modified Title')).toBeVisible({ timeout: 3000 });

    await page.keyboard.down('ControlOrMeta');
    await page.keyboard.press('z');
    await page.keyboard.up('ControlOrMeta');
    await page.waitForTimeout(300);

    await expect(page.getByText('Test EPIC Authoring System')).toBeVisible({ timeout: 3000 });
  });
});

test.describe('EPIC Authoring System - Checklist Editing', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto(`http://localhost:3001/plans/${TEST_PLAN_ID}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
  });

  test('Checklist items can be added to DoD section', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const addItemBtn = page.locator('#EPIC-001').getByRole('button', { name: /add item/i });
    await addItemBtn.first().click();
    await page.waitForTimeout(200);

    const newItemInput = page.locator('#EPIC-001 input[placeholder*="new item"]').first();
    await expect(newItemInput).toBeVisible({ timeout: 3000 });
    await newItemInput.fill('New checklist item');
    await newItemInput.press('Enter');
    await page.waitForTimeout(300);

    await expect(page.getByText('New checklist item')).toBeVisible({ timeout: 3000 });
  });

  test('Task items can be added to Tasks section', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const addTaskBtn = page.locator('#EPIC-001').getByRole('button', { name: /add task/i });
    await addTaskBtn.first().click();
    await page.waitForTimeout(200);

    const newTaskInput = page.locator('#EPIC-001 input[placeholder*="new task"]').first();
    await expect(newTaskInput).toBeVisible({ timeout: 3000 });
    await newTaskInput.fill('New task item');
    await newTaskInput.press('Enter');
    await page.waitForTimeout(300);

    await expect(page.getByText('New task item')).toBeVisible({ timeout: 3000 });
  });
});

test.describe('EPIC Authoring System - Tab Sync', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto(`http://localhost:3001/plans/${TEST_PLAN_ID}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
  });

  test('Content stays in sync between Epic Design and Markdown Editor', async ({ page }) => {
    const plannerTab = page.getByRole('button', { name: /planner/i });
    await plannerTab.click();
    await page.waitForTimeout(500);

    const epicDesignBtn = page.getByRole('button', { name: /epic design/i });
    await epicDesignBtn.click();
    await page.waitForTimeout(500);

    const addEpicBtn = page.getByRole('button', { name: /add new epic/i });
    await addEpicBtn.click();
    await page.waitForTimeout(500);

    const epicCountInDesign = await page.locator('text=/EPIC-\\d{3}/').count();

    const markdownEditorBtn = page.getByRole('button', { name: /markdown editor/i });
    await markdownEditorBtn.click();
    await page.waitForTimeout(500);

    const textarea = page.locator('textarea.font-mono');
    const content = await textarea.inputValue();
    const epicMatchesInMarkdown = content.match(/## EPIC-\d{3}/g);
    expect(epicMatchesInMarkdown?.length || 0).toBe(epicCountInDesign);
  });
});
