# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ux-coherence.spec.ts >> UX Coherence >> 12: view-state-consistency
- Location: tests/ux-coherence.spec.ts:39:7

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 4
Received: 8
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
      - textbox "Describe the mood, genre, or style you want to explore..." [disabled] [ref=e12]: Dream pop in A major, wistful, 4 bars
      - button "Running..." [disabled] [ref=e13]
    - generic [ref=e14]:
      - generic [ref=e15]: Mode
      - generic [ref=e16]:
        - button "Conservative" [disabled] [ref=e17]
        - button "Balanced" [disabled] [ref=e18]
        - button "Exploratory" [disabled] [ref=e19]
    - generic [ref=e23]:
      - generic [ref=e24]: Intent
      - generic [ref=e25]: Genre
      - generic [ref=e26]: Memory
      - generic [ref=e27]: Generate
      - generic [ref=e28]: Evaluate
      - generic [ref=e29]: Select
      - generic [ref=e30]: Context
      - generic [ref=e31]: Voicings
      - generic [ref=e32]: Bass
      - generic [ref=e33]: Assemble
      - generic [ref=e34]: Eval Arr.
      - generic [ref=e35]: Rank
      - generic [ref=e36]: Check
      - generic [ref=e37]: Save
      - generic [ref=e38]: Done
  - generic [ref=e39]:
    - heading "4 candidates" [level=2] [ref=e40]
    - generic [ref=e41]:
      - generic [ref=e42] [cursor=pointer]:
        - generic [ref=e43]:
          - generic [ref=e44]: A
          - generic [ref=e46]: "0.0"
        - generic [ref=e47]:
          - paragraph [ref=e48]: Amaj7 → F#m7 → Dmaj7 → E7
          - paragraph [ref=e49]: Imaj7 → vi7 → IVmaj7 → V
        - generic [ref=e50]:
          - generic [ref=e51]: A major
          - generic [ref=e52]: wistful
          - generic [ref=e53]: ethereal
        - paragraph [ref=e54]: Classic dream pop I-vi-IV-V with 7th extensions
        - button "Realize" [ref=e55]
      - generic [ref=e56] [cursor=pointer]:
        - generic [ref=e57]:
          - generic [ref=e58]: B
          - generic [ref=e60]: "0.0"
        - generic [ref=e61]:
          - paragraph [ref=e62]: F#m7 → Dmaj7 → Amaj7 → E7
          - paragraph [ref=e63]: vi7 → IVmaj7 → Imaj7 → V
        - generic [ref=e64]:
          - generic [ref=e65]: A major
          - generic [ref=e66]: haunted
          - generic [ref=e67]: atmospheric
        - paragraph [ref=e68]: Minor-start for darker mood
        - button "Realize" [ref=e69]
      - generic [ref=e70] [cursor=pointer]:
        - generic [ref=e71]:
          - generic [ref=e72]: C
          - generic [ref=e74]: "0.0"
        - generic [ref=e75]:
          - paragraph [ref=e76]: Amaj7 → F#m7 → Dmaj7 → E7
          - paragraph [ref=e77]: Imaj7 → vi7 → IVmaj7 → V
        - generic [ref=e78]:
          - generic [ref=e79]: A major
          - generic [ref=e80]: wistful
          - generic [ref=e81]: ethereal
        - paragraph [ref=e82]: Classic dream pop I-vi-IV-V with 7th extensions
        - button "Realize" [ref=e83]
      - generic [ref=e84] [cursor=pointer]:
        - generic [ref=e85]:
          - generic [ref=e86]: D
          - generic [ref=e88]: "0.0"
        - generic [ref=e89]:
          - paragraph [ref=e90]: Amaj7 → F#m7 → Dmaj7 → E7
          - paragraph [ref=e91]: Imaj7 → vi7 → IVmaj7 → V
        - generic [ref=e92]:
          - generic [ref=e93]: A major
          - generic [ref=e94]: wistful
          - generic [ref=e95]: ethereal
        - paragraph [ref=e96]: Classic dream pop I-vi-IV-V with 7th extensions
        - button "Realize" [ref=e97]
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
> 50 |     expect(await cards.count()).toBe(headingCount);
     |                                 ^ Error: expect(received).toBe(expected) // Object.is equality
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
  67 |     await expect(genButton).toBeDisabled();
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