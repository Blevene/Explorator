# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ux-coherence.spec.ts >> UX Coherence >> 11: navigation-flow
- Location: tests/ux-coherence.spec.ts:4:7

# Error details

```
Error: locator.click: Error: strict mode violation: getByText('Back to progressions').or(getByText('Back')) resolved to 3 elements:
    1) <a href="/" data-discover="true" class="text-xs font-medium transition-colors">← Back</a> aka getByRole('link', { name: '← Back' })
    2) <button class="text-xs font-medium mb-2 transition-colors">← Back to progressions</button> aka getByRole('button', { name: '← Back to progressions' })
    3) <h3 class="text-xs font-semibold uppercase tracking-wider">Feedback</h3> aka getByRole('heading', { name: 'Feedback' })

Call log:
  - waiting for getByText('Back to progressions').or(getByText('Back'))

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - generic [ref=e4]:
    - link "← Back" [ref=e5] [cursor=pointer]:
      - /url: /
    - generic [ref=e6]:
      - heading "Navigation test, dream pop, 4 bars" [level=1] [ref=e7]
      - paragraph [ref=e8]: full_exploration · active
  - generic [ref=e10]:
    - generic [ref=e11]:
      - textbox "Describe the mood, genre, or style you want to explore..." [disabled] [ref=e12]: Navigation test, dream pop, 4 bars
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
      - paragraph [ref=e44]: F#m7 → Dmaj7 → Amaj7 → E7
      - generic [ref=e45]:
        - generic [ref=e46] [cursor=pointer]:
          - generic [ref=e47]:
            - generic [ref=e48]: "#1"
            - generic [ref=e49]: "6.23"
          - generic [ref=e50]:
            - generic [ref=e51]: drop2
            - generic [ref=e52]: supportive bass
        - generic [ref=e53] [cursor=pointer]:
          - generic [ref=e54]:
            - generic [ref=e55]: "#2"
            - generic [ref=e56]: "6.23"
          - generic [ref=e57]:
            - generic [ref=e58]: drop2
            - generic [ref=e59]: pedal bass
        - generic [ref=e60] [cursor=pointer]:
          - generic [ref=e61]:
            - generic [ref=e62]: "#3"
            - generic [ref=e63]: "6.02"
          - generic [ref=e64]:
            - generic [ref=e65]: open
            - generic [ref=e66]: supportive bass
        - generic [ref=e67] [cursor=pointer]:
          - generic [ref=e68]:
            - generic [ref=e69]: "#3"
            - generic [ref=e70]: "6.02"
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
            - generic [ref=e108]: "6.23"
          - button "Collapse scores" [ref=e109]: −
        - generic [ref=e110]:
          - generic [ref=e111]:
            - generic [ref=e112]: Arrangement
            - generic [ref=e113]:
              - generic [ref=e114]: voice leading
              - generic [ref=e117]: "8.0"
            - generic [ref=e118]:
              - generic [ref=e119]: register density
              - generic [ref=e122]: "10.0"
            - generic [ref=e123]:
              - generic [ref=e124]: playability
              - generic [ref=e127]: "9.8"
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
      - generic [ref=e166]:
        - textbox "\"more experimental\"" [ref=e167]
        - button "Send" [disabled] [ref=e168]
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
> 24 |     await page.getByText('Back to progressions').or(page.getByText('Back')).click();
     |                                                                             ^ Error: locator.click: Error: strict mode violation: getByText('Back to progressions').or(getByText('Back')) resolved to 3 elements:
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