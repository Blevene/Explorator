# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ux-coherence.spec.ts >> UX Coherence >> 13: interaction-affordances
- Location: tests/ux-coherence.spec.ts:62:7

# Error details

```
Error: expect(locator).toBeDisabled() failed

Locator:  getByRole('button', { name: /generate/i })
Expected: disabled
Received: enabled
Timeout:  10000ms

Call log:
  - Expect "toBeDisabled" with timeout 10000ms
  - waiting for getByRole('button', { name: /generate/i })
    14 × locator resolved to <button class="px-5 py-2 rounded-lg font-medium text-sm transition-all disabled:opacity-30">Generate</button>
       - unexpected value "enabled"

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - generic [ref=e4]:
    - link "← Back" [ref=e5] [cursor=pointer]:
      - /url: /
    - generic [ref=e6]:
      - heading "Dream pop in A major, wistful, 4 bars" [level=1] [ref=e7]
      - paragraph [ref=e8]: full_exploration · active
  - generic [ref=e10]:
    - generic [ref=e11]:
      - textbox "Describe the mood, genre, or style you want to explore..." [ref=e12]: Dream pop in A major, wistful, 4 bars
      - button "Generate" [ref=e13]
    - generic [ref=e14]:
      - generic [ref=e15]: Mode
      - generic [ref=e16]:
        - button "Conservative" [ref=e17]
        - button "Balanced" [ref=e18]
        - button "Exploratory" [ref=e19]
  - generic [ref=e20]: No candidates yet. Enter a prompt above and click Generate to start exploring.
```

# Test source

```ts
  1  | import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';
  2  | 
  3  | test.describe('UX Coherence', () => {
  4  |   test('11: navigation-flow', async ({ page }) => {
  5  |     await page.goto('/');
  6  |     await expect(page.locator('text=Explorator')).toBeVisible();
  7  | 
  8  |     // Create session
  9  |     await page.locator('input').first().fill('Navigation test, dream pop, 4 bars');
  10 |     await page.getByRole('button', { name: /explore/i }).click();
  11 |     await page.waitForURL(/\/session\//);
  12 | 
  13 |     // Generate
  14 |     const promptInput = page.locator('input').first();
  15 |     await promptInput.fill('Navigation test, dream pop, 4 bars');
  16 |     await page.getByRole('button', { name: /generate/i }).click();
  17 |     await page.locator('text=→').first().waitFor({ timeout: 30_000 });
  18 | 
  19 |     // Realize
  20 |     await page.getByRole('button', { name: /realize/i }).first().click();
  21 |     await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 30_000 });
  22 | 
  23 |     // Back to progressions
  24 |     await page.getByText('Back to progressions').or(page.getByText('Back')).click();
  25 |     await page.waitForTimeout(500);
  26 | 
  27 |     // Candidates still there
  28 |     expect(await page.locator('text=→').count()).toBeGreaterThan(0);
  29 | 
  30 |     // No orphaned spinners
  31 |     await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  32 | 
  33 |     // Back to dashboard
  34 |     await page.getByText('Back').first().click();
  35 |     await page.waitForURL('/');
  36 |     await expect(page.locator('text=Explorator')).toBeVisible();
  37 |   });
  38 | 
  39 |   test('12: view-state-consistency', async ({ page, testSession }) => {
  40 |     await goToWorkspace(page, testSession.sessionId);
  41 |     await generateCandidates(page, testSession.prompt);
  42 | 
  43 |     // Count heading
  44 |     const heading = page.locator('text=/\\d+ candidate/');
  45 |     const headingText = await heading.textContent() ?? '';
  46 |     const headingCount = parseInt(headingText.match(/(\d+)/)?.[1] ?? '0');
  47 | 
  48 |     // Count actual cards
  49 |     const cards = page.locator('text=→');
  50 |     expect(await cards.count()).toBe(headingCount);
  51 | 
  52 |     // Realize and go back
  53 |     await realizeFirstCandidate(page);
  54 |     await page.getByText('Back to progressions').or(page.getByText('Back')).click();
  55 |     await page.waitForTimeout(500);
  56 | 
  57 |     // Candidates still present
  58 |     expect(await page.locator('text=→').count()).toBe(headingCount);
  59 |     await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  60 |   });
  61 | 
  62 |   test('13: interaction-affordances', async ({ page, testSession }) => {
  63 |     await goToWorkspace(page, testSession.sessionId);
  64 | 
  65 |     // Generate button disabled when empty
  66 |     const genButton = page.getByRole('button', { name: /generate/i });
> 67 |     await expect(genButton).toBeDisabled();
     |                             ^ Error: expect(locator).toBeDisabled() failed
  68 | 
  69 |     // Fill and generate
  70 |     await page.locator('input').first().fill(testSession.prompt);
  71 |     await genButton.click();
  72 | 
  73 |     // While running: button + input disabled
  74 |     await expect(genButton).toBeDisabled();
  75 | 
  76 |     // Wait for completion
  77 |     await page.locator('text=→').first().waitFor({ timeout: 30_000 });
  78 | 
  79 |     // After: button re-enabled
  80 |     await expect(genButton).not.toBeDisabled();
  81 |   });
  82 | });
  83 | 
```