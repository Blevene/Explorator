# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: pipeline.spec.ts >> Pipeline & SSE >> 14: sse-stream-completion
- Location: tests/pipeline.spec.ts:4:7

# Error details

```
Error: expect(locator).not.toBeDisabled() failed

Locator: getByRole('button', { name: /generate/i })
Expected: not disabled
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "not toBeDisabled" with timeout 10000ms
  - waiting for getByRole('button', { name: /generate/i })

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
  1  | import { test, expect, goToWorkspace, generateCandidates } from '../fixtures/test-fixtures';
  2  | 
  3  | test.describe('Pipeline & SSE', () => {
  4  |   test('14: sse-stream-completion', async ({ page, testSession }) => {
  5  |     await goToWorkspace(page, testSession.sessionId);
  6  | 
  7  |     await page.locator('input').first().fill(testSession.prompt);
  8  |     await page.getByRole('button', { name: /generate/i }).click();
  9  | 
  10 |     // Wait for candidates
  11 |     await page.locator('text=→').first().waitFor({ timeout: 30_000 });
  12 | 
  13 |     // Loading cleared, button re-enabled
> 14 |     await expect(page.getByRole('button', { name: /generate/i })).not.toBeDisabled();
     |                                                                       ^ Error: expect(locator).not.toBeDisabled() failed
  15 | 
  16 |     // No error messages
  17 |     await expect(page.locator('text=timed out')).toBeHidden();
  18 |     await expect(page.locator('text=Error').first()).toBeHidden();
  19 |   });
  20 | 
  21 |   test('15: multi-round-generation', async ({ page, testSession }) => {
  22 |     await goToWorkspace(page, testSession.sessionId);
  23 |     await generateCandidates(page, testSession.prompt);
  24 | 
  25 |     const count1 = await page.locator('text=→').count();
  26 |     expect(count1).toBeGreaterThan(0);
  27 | 
  28 |     // Generate round 2
  29 |     await page.locator('input').first().fill('More dreamy, add suspensions');
  30 |     await page.getByRole('button', { name: /generate/i }).click();
  31 |     await page.waitForTimeout(2_000);
  32 |     await page.locator('text=→').first().waitFor({ timeout: 60_000 });
  33 | 
  34 |     // Candidates should still exist
  35 |     expect(await page.locator('text=→').count()).toBeGreaterThanOrEqual(count1);
  36 |   });
  37 | 
  38 |   test('16: generation-mode-switching', async ({ page, testSession }) => {
  39 |     await goToWorkspace(page, testSession.sessionId);
  40 | 
  41 |     // Select exploratory mode
  42 |     await page.getByRole('button', { name: /exploratory/i }).click();
  43 | 
  44 |     await generateCandidates(page, testSession.prompt);
  45 | 
  46 |     // Mode button still visible
  47 |     await expect(page.getByRole('button', { name: /exploratory/i })).toBeVisible();
  48 |   });
  49 | });
  50 | 
```