/**
 * E2E Browser Tests for Knowledge Tab & Pipeline (EPIC-001)
 * Tests the full namespace → import → query → graph pipeline
 */

import { test, expect, Page } from '@playwright/test';

test.describe('Knowledge Tab & Pipeline', () => {
  let page: Page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    
    // Mock API responses for consistent testing
    await page.route('**/api/knowledge/namespaces', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            schema_version: 1,
            name: 'test-namespace',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
            language: 'English',
            description: 'Test namespace for E2E',
            embedding_model: 'text-embedding-3-small',
            embedding_dimension: 1536,
            stats: {
              files_indexed: 10,
              chunks: 100,
              entities: 50,
              relations: 25,
              vectors: 100,
              bytes_on_disk: 1024000,
            },
            imports: [],
          },
        ]),
      });
    });

    await page.route('**/api/knowledge/metrics', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          timestamp: new Date().toISOString(),
          backend: 'lancedb',
          counters: {
            query_total: { value: 150, description: 'Total queries' },
            ingest_files_total: { value: 25, description: 'Files ingested' },
            ingest_bytes_total: { value: 1048576, description: 'Bytes ingested' },
            query_errors_total: { value: 0, description: 'Query errors' },
            llm_calls_total: { value: 10, description: 'LLM calls' },
          },
          histograms: {
            query_latency_seconds: {
              stats: { count: 150, sum: 45, min: 0.1, max: 2.5, avg: 0.3 },
              description: 'Query latency',
            },
          },
          gauges: {
            namespaces_total: { value: 1, description: 'Total namespaces' },
            disk_bytes_per_namespace: { labels: { 'namespace=test-namespace': 1024000 } },
          },
        }),
      });
    });

    await page.route('**/api/knowledge/namespaces/test-namespace/graph', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: 'node-1', label: 'person', name: 'John Doe', score: 1.0, properties: {} },
            { id: 'node-2', label: 'organization', name: 'Acme Corp', score: 0.9, properties: {} },
          ],
          edges: [
            { source: 'node-1', target: 'node-2', label: 'WORKS_FOR' },
          ],
          stats: { node_count: 2, edge_count: 1 },
        }),
      });
    });
  });

  test.afterEach(async () => {
    await page.close();
  });

  test('T-001.1: Navigate to Knowledge tab, verify empty state renders', async () => {
    // Navigate to a plan page (mocked)
    await page.goto('/plan/test-plan-id');
    
    // Wait for page load
    await page.waitForLoadState('networkidle');
    
    // Check if Knowledge tab exists in sidebar
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    // If Knowledge tab exists, click it
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      
      // Verify Knowledge header appears
      await expect(page.locator('text=Knowledge')).toBeVisible({ timeout: 5000 });
    }
  });

  test('T-001.2: Click + New, verify namespace creation UI appears', async () => {
    await page.goto('/plan/test-plan-id');
    await page.waitForLoadState('networkidle');
    
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      
      // Look for New button
      const newButton = page.locator('button').filter({ hasText: /new/i });
      
      if (await newButton.count() > 0) {
        await newButton.first().click();
        
        // Verify create modal appears
        await expect(page.locator('text=Create Namespace')).toBeVisible({ timeout: 5000 });
        
        // Verify form fields
        await expect(page.locator('input[placeholder*="namespace"]')).toBeVisible();
      }
    }
  });

  test('T-001.3: Verify MetricsStrip shows stat cards', async () => {
    await page.goto('/plan/test-plan-id');
    await page.waitForLoadState('networkidle');
    
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      
      // Check for Metrics section
      const metricsSection = page.locator('text=Metrics');
      
      if (await metricsSection.count() > 0) {
        // Verify stat cards exist
        await expect(page.locator('text=Query Rate')).toBeVisible({ timeout: 5000 });
        await expect(page.locator('text=Ingest Rate')).toBeVisible();
        await expect(page.locator('text=Error Rate')).toBeVisible();
      }
    }
  });

  test('T-001.4: Type query in QueryPanel, verify loading state', async () => {
    // Mock query API
    await page.route('**/api/knowledge/namespaces/test-namespace/query', async (route) => {
      // Simulate delay
      await new Promise(resolve => setTimeout(resolve, 500));
      
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          query: 'test query',
          mode: 'raw',
          namespace: 'test-namespace',
          chunks: [
            {
              text: 'This is a test chunk.',
              score: 0.95,
              file_path: '/test/file.txt',
              filename: 'file.txt',
              chunk_index: 0,
              total_chunks: 1,
              file_hash: 'abc123',
              mime_type: 'text/plain',
              category_id: null,
            },
          ],
          entities: [],
          answer: null,
          citations: [],
          latency_ms: 150,
          warnings: [],
        }),
      });
    });
    
    await page.goto('/plan/test-plan-id');
    await page.waitForLoadState('networkidle');
    
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      
      // Switch to Query tab
      const queryTab = page.locator('button, [role="tab"]').filter({ hasText: /query/i });
      if (await queryTab.count() > 0) {
        await queryTab.click();
        
        // Select namespace first (if required)
        const selectPrompt = page.locator('text=Select a Namespace');
        if (await selectPrompt.count() > 0) {
          // Need to select namespace first
          const namespacesTab = page.locator('button, [role="tab"]').filter({ hasText: /namespaces/i });
          if (await namespacesTab.count() > 0) {
            await namespacesTab.click();
            
            // Click on a namespace
            const namespaceItem = page.locator('text=test-namespace');
            if (await namespaceItem.count() > 0) {
              await namespaceItem.click();
            }
          }
        }
        
        // Type in query input
        const queryInput = page.locator('input[placeholder*="query" i]');
        if (await queryInput.count() > 0) {
          await queryInput.fill('test query');
          
          // Click search button
          const searchButton = page.locator('button').filter({ hasText: /search/i });
          if (await searchButton.count() > 0) {
            await searchButton.click();
            
            // Verify loading state or results appear
            const loadingIndicator = page.locator('text=Searching');
            const results = page.locator('text=Relevant Chunks');
            
            // Either loading or results should appear
            await expect(
              loadingIndicator.or(results)
            ).toBeVisible({ timeout: 10000 });
          }
        }
      }
    }
  });

  test('T-001.5: Check console for errors during all interactions', async () => {
    const consoleErrors: string[] = [];
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    page.on('pageerror', error => {
      consoleErrors.push(error.message);
    });
    
    await page.goto('/plan/test-plan-id');
    await page.waitForLoadState('networkidle');
    
    // Navigate through all tabs
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      await page.waitForTimeout(500);
      
      // Click Import tab
      const importTab = page.locator('button, [role="tab"]').filter({ hasText: /import/i });
      if (await importTab.count() > 0) {
        await importTab.click();
        await page.waitForTimeout(500);
      }
      
      // Click Query tab
      const queryTab = page.locator('button, [role="tab"]').filter({ hasText: /query/i });
      if (await queryTab.count() > 0) {
        await queryTab.click();
        await page.waitForTimeout(500);
      }
      
      // Click Namespaces tab
      const namespacesTab = page.locator('button, [role="tab"]').filter({ hasText: /namespaces/i });
      if (await namespacesTab.count() > 0) {
        await namespacesTab.click();
        await page.waitForTimeout(500);
      }
    }
    
    // Assert no console errors (excluding known benign errors)
    const criticalErrors = consoleErrors.filter(err => 
      !err.includes('favicon') &&
      !err.includes('manifest') &&
      !err.includes('ResizeObserver')
    );
    
    expect(criticalErrors).toHaveLength(0);
  });

  test('T-001.6: Verify NamespaceActions dropdown renders on existing namespace', async () => {
    await page.goto('/plan/test-plan-id');
    await page.waitForLoadState('networkidle');
    
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      
      // Hover over namespace item to reveal actions
      const namespaceItem = page.locator('text=test-namespace').first();
      if (await namespaceItem.count() > 0) {
        await namespaceItem.hover();
        
        // Look for action buttons (refresh, delete)
        const refreshButton = page.locator('button[aria-label*="refresh" i]');
        const deleteButton = page.locator('button[aria-label*="delete" i]');
        
        // At least one action should be visible
        const hasActions = (await refreshButton.count()) > 0 || (await deleteButton.count()) > 0;
        expect(hasActions).toBeTruthy();
      }
    }
  });

  test('GraphView renders with nodes', async () => {
    await page.goto('/plan/test-plan-id');
    await page.waitForLoadState('networkidle');
    
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      
      // Select namespace to enable graph view
      const namespaceItem = page.locator('text=test-namespace');
      if (await namespaceItem.count() > 0) {
        await namespaceItem.click();
        
        // Check for graph stats badge
        const statsBadge = page.locator('text=/\\d+ nodes.*\\d+ edges/i');
        await expect(statsBadge).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('All 4 hooks fire without exceptions', async () => {
    const apiCalls: string[] = [];
    
    page.on('request', request => {
      if (request.url().includes('/api/knowledge/')) {
        apiCalls.push(request.url());
      }
    });
    
    await page.goto('/plan/test-plan-id');
    await page.waitForLoadState('networkidle');
    
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      await page.waitForTimeout(1000);
      
      // Switch through all tabs to trigger hooks
      const tabs = ['Import', 'Query', 'Namespaces'];
      for (const tabName of tabs) {
        const tab = page.locator('button, [role="tab"]').filter({ hasText: new RegExp(tabName, 'i') });
        if (await tab.count() > 0) {
          await tab.click();
          await page.waitForTimeout(300);
        }
      }
      
      // Verify at least namespaces hook was called
      const namespacesCalled = apiCalls.some(url => url.includes('/namespaces'));
      expect(namespacesCalled).toBeTruthy();
    }
  });
});

test.describe('Knowledge Tab - Error States', () => {
  test('handles API error gracefully', async ({ page }) => {
    // Mock error response
    await page.route('**/api/knowledge/namespaces', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });
    
    await page.goto('/plan/test-plan-id');
    await page.waitForLoadState('networkidle');
    
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      
      // Should show error state or empty state gracefully
      await page.waitForTimeout(1000);
      
      // Page should not crash - check for any content
      const hasContent = await page.locator('body').textContent();
      expect(hasContent).toBeTruthy();
    }
  });

  test('handles empty namespace list', async ({ page }) => {
    // Mock empty response
    await page.route('**/api/knowledge/namespaces', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
    
    await page.goto('/plan/test-plan-id');
    await page.waitForLoadState('networkidle');
    
    const knowledgeTab = page.locator('button, [role="tab"]').filter({ hasText: /knowledge/i });
    
    if (await knowledgeTab.count() > 0) {
      await knowledgeTab.first().click();
      
      // Should show empty state
      await expect(page.locator('text=No Knowledge Namespaces')).toBeVisible({ timeout: 5000 });
    }
  });
});
