# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: m3-features.spec.ts >> M3 Features >> 5: mutation-flow
- Location: tests/m3-features.spec.ts:22:7

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: locator.click: Test timeout of 60000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: /mutate/i }).first()

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
  3  | test.describe('M3 Features', () => {
  4  |   test('4: feedback-submission', async ({ page, testSession }) => {
  5  |     await goToWorkspace(page, testSession.sessionId);
  6  |     await generateCandidates(page, testSession.prompt);
  7  |     await realizeFirstCandidate(page);
  8  | 
  9  |     // Select an arrangement
  10 |     await page.locator('[class*="cursor-pointer"]').filter({ hasText: /\d+\.\d/ }).first().click();
  11 | 
  12 |     // Submit feedback
  13 |     const feedbackInput = page.locator('input[placeholder*="experimental"]')
  14 |       .or(page.locator('input[placeholder*="more"]'));
  15 |     await feedbackInput.fill('more experimental, less predictable');
  16 |     await page.getByRole('button', { name: /send/i }).click();
  17 | 
  18 |     await expect(page.locator('text=Understood')).toBeVisible({ timeout: 15_000 });
  19 |     await expect(page.locator('text=Weights').or(page.locator('text=Genre Fit'))).toBeVisible();
  20 |   });
  21 | 
  22 |   test('5: mutation-flow', async ({ page, testSession }) => {
  23 |     await goToWorkspace(page, testSession.sessionId);
  24 |     await generateCandidates(page, testSession.prompt);
  25 | 
> 26 |     await page.getByRole('button', { name: /mutate/i }).first().click();
     |                                                                 ^ Error: locator.click: Test timeout of 60000ms exceeded.
  27 |     await expect(page.locator('text=Mutate Candidate')).toBeVisible();
  28 | 
  29 |     await page.locator('input[placeholder*="darker"]')
  30 |       .or(page.locator('input[placeholder*="tension"]'))
  31 |       .fill('make it darker');
  32 |     await page.locator('button:has-text("Mutate")').last().click();
  33 | 
  34 |     // Wait and reload to see results
  35 |     await page.waitForTimeout(5_000);
  36 |     await page.reload();
  37 |     await page.waitForTimeout(2_000);
  38 | 
  39 |     await expect(page.locator('text=mutated')).toBeVisible({ timeout: 10_000 });
  40 |     await expect(page.locator('text=Mutation Lineage')).toBeVisible();
  41 |   });
  42 | 
  43 |   test('6: finalist-panel', async ({ page, testSession }) => {
  44 |     await goToWorkspace(page, testSession.sessionId);
  45 |     await generateCandidates(page, testSession.prompt);
  46 |     await realizeFirstCandidate(page);
  47 | 
  48 |     await expect(page.locator('text=Finalists')).toBeVisible({ timeout: 10_000 });
  49 |     const badges = page.locator('text=Safest')
  50 |       .or(page.locator('text=Best Loop'))
  51 |       .or(page.locator('text=Most Experimental'));
  52 |     await expect(badges.first()).toBeVisible();
  53 |   });
  54 | 
  55 |   test('7: realization-caching', async ({ page, testSession }) => {
  56 |     await goToWorkspace(page, testSession.sessionId);
  57 |     await generateCandidates(page, testSession.prompt);
  58 |     await realizeFirstCandidate(page);
  59 | 
  60 |     // Go back
  61 |     await page.getByText('Back to progressions').or(page.getByText('Back')).click();
  62 |     await page.waitForTimeout(500);
  63 | 
  64 |     // Realize same candidate again — should be instant
  65 |     const start = Date.now();
  66 |     await page.getByRole('button', { name: /realize/i }).first().click();
  67 |     await page.locator('canvas').waitFor({ timeout: 5_000 });
  68 |     expect(Date.now() - start).toBeLessThan(3_000);
  69 |   });
  70 | });
  71 | 
```