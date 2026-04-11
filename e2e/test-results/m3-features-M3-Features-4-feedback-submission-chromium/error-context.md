# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: m3-features.spec.ts >> M3 Features >> 4: feedback-submission
- Location: tests/m3-features.spec.ts:4:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('text=Understood')
Expected: visible
Timeout: 15000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 15000ms
  - waiting for locator('text=Understood')

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
  - button "← Back to progressions" [ref=e39]
  - generic [ref=e40]:
    - generic [ref=e42]:
      - paragraph [ref=e44]: Amaj7 → F#m7 → Dmaj7 → E7
      - generic [ref=e45]:
        - generic [ref=e46] [cursor=pointer]:
          - generic [ref=e47]:
            - generic [ref=e48]: "#1"
            - generic [ref=e49]: "6.34"
          - generic [ref=e50]:
            - generic [ref=e51]: drop2
            - generic [ref=e52]: supportive bass
        - generic [ref=e53] [cursor=pointer]:
          - generic [ref=e54]:
            - generic [ref=e55]: "#2"
            - generic [ref=e56]: "6.34"
          - generic [ref=e57]:
            - generic [ref=e58]: drop2
            - generic [ref=e59]: pedal bass
        - generic [ref=e60] [cursor=pointer]:
          - generic [ref=e61]:
            - generic [ref=e62]: "#3"
            - generic [ref=e63]: "6.27"
          - generic [ref=e64]:
            - generic [ref=e65]: open
            - generic [ref=e66]: supportive bass
        - generic [ref=e67] [cursor=pointer]:
          - generic [ref=e68]:
            - generic [ref=e69]: "#3"
            - generic [ref=e70]: "6.27"
          - generic [ref=e71]:
            - generic [ref=e72]: open
            - generic [ref=e73]: pedal bass
    - generic [ref=e74]:
      - generic [ref=e75]:
        - button "Play" [ref=e76]:
          - img [ref=e77]
        - button "Stop" [ref=e79]:
          - img [ref=e80]
        - generic [ref=e83]:
          - generic [ref=e84]: BPM
          - 'slider "Tempo: 120 BPM" [ref=e85] [cursor=pointer]': "120"
          - generic [ref=e86]: "120"
        - button "Loop on" [ref=e88]:
          - img [ref=e89]
        - button "V" [ref=e94]
        - button "B" [ref=e95]
        - generic [ref=e97]:
          - generic [ref=e98]: Vol
          - 'slider "Volume: -6 dB" [ref=e99] [cursor=pointer]': "-6"
          - generic [ref=e100]: "-6 dB"
      - generic [ref=e104]:
        - generic [ref=e105]:
          - generic [ref=e106]:
            - generic [ref=e107]: Scores
            - generic [ref=e108]: "6.34"
          - button "Collapse scores" [ref=e109]: −
        - generic [ref=e110]:
          - generic [ref=e111]:
            - generic [ref=e112]: Arrangement
            - generic [ref=e113]:
              - generic [ref=e114]: voice leading
              - generic [ref=e117]: "9.2"
            - generic [ref=e118]:
              - generic [ref=e119]: register density
              - generic [ref=e122]: "10.0"
            - generic [ref=e123]:
              - generic [ref=e124]: playability
              - generic [ref=e127]: "9.3"
          - generic [ref=e128]:
            - generic [ref=e129]: Progression
            - generic [ref=e130]:
              - generic [ref=e131]: genre fit
              - generic [ref=e134]: "5.0"
            - generic [ref=e135]:
              - generic [ref=e136]: emotional fit
              - generic [ref=e139]: "5.0"
            - generic [ref=e140]:
              - generic [ref=e141]: theoretical coherence
              - generic [ref=e144]: "5.0"
            - generic [ref=e145]:
              - generic [ref=e146]: cadence quality
              - generic [ref=e149]: "5.0"
            - generic [ref=e150]:
              - generic [ref=e151]: novelty
              - generic [ref=e154]: "5.0"
            - generic [ref=e155]:
              - generic [ref=e156]: loopability
              - generic [ref=e159]: "5.0"
    - generic [ref=e160]:
      - heading "Feedback" [level=3] [ref=e162]
      - paragraph [ref=e164]: Type below to steer the search.
      - generic [ref=e165]: "Feedback submission failed: 500"
      - generic [ref=e167]:
        - textbox "\"more experimental\"" [ref=e168]
        - button "Send" [disabled] [ref=e169]
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
> 18 |     await expect(page.locator('text=Understood')).toBeVisible({ timeout: 15_000 });
     |                                                   ^ Error: expect(locator).toBeVisible() failed
  19 |     await expect(page.locator('text=Weights').or(page.locator('text=Genre Fit'))).toBeVisible();
  20 |   });
  21 | 
  22 |   test('5: mutation-flow', async ({ page, testSession }) => {
  23 |     await goToWorkspace(page, testSession.sessionId);
  24 |     await generateCandidates(page, testSession.prompt);
  25 | 
  26 |     await page.getByRole('button', { name: /mutate/i }).first().click();
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