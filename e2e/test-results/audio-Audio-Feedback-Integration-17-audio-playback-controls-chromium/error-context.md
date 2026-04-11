# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audio.spec.ts >> Audio & Feedback Integration >> 17: audio-playback-controls
- Location: tests/audio.spec.ts:4:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('button:has-text("V")')
Expected: visible
Error: strict mode violation: locator('button:has-text("V")') resolved to 2 elements:
    1) <button disabled class="text-xs px-3 py-1 rounded transition-colors disabled:opacity-40">Conservative</button> aka getByRole('button', { name: 'Conservative' })
    2) <button title="Mute voicing" class="px-2 py-1 rounded text-xs font-bold transition-colors">V</button> aka getByRole('button', { name: 'V', exact: true })

Call log:
  - Expect "toBeVisible" with timeout 10000ms
  - waiting for locator('button:has-text("V")')

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
      - generic [ref=e166]:
        - textbox "\"more experimental\"" [ref=e167]
        - button "Send" [disabled] [ref=e168]
```

# Test source

```ts
  1  | import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';
  2  | 
  3  | test.describe('Audio & Feedback Integration', () => {
  4  |   test('17: audio-playback-controls', async ({ page, testSession }) => {
  5  |     await goToWorkspace(page, testSession.sessionId);
  6  |     await generateCandidates(page, testSession.prompt);
  7  |     await realizeFirstCandidate(page);
  8  | 
  9  |     // Transport bar elements
  10 |     await expect(page.locator('text=BPM')).toBeVisible();
  11 |     await expect(page.locator('text=Vol')).toBeVisible();
> 12 |     await expect(page.locator('button:has-text("V")')).toBeVisible();
     |                                                        ^ Error: expect(locator).toBeVisible() failed
  13 |     await expect(page.locator('button:has-text("B")')).toBeVisible();
  14 | 
  15 |     // Toggle voicing mute
  16 |     await page.locator('button:has-text("V")').click();
  17 |     await page.waitForTimeout(200);
  18 | 
  19 |     // Toggle bass mute
  20 |     await page.locator('button:has-text("B")').click();
  21 |     await page.waitForTimeout(200);
  22 | 
  23 |     // No JS errors should have occurred (Playwright captures uncaught)
  24 |   });
  25 | 
  26 |   test('18: feedback-affects-next-round', async ({ page, testSession }) => {
  27 |     await goToWorkspace(page, testSession.sessionId);
  28 |     await generateCandidates(page, testSession.prompt);
  29 |     await realizeFirstCandidate(page);
  30 | 
  31 |     // Select arrangement
  32 |     await page.locator('[class*="cursor-pointer"]').filter({ hasText: /\d+\.\d/ }).first().click();
  33 | 
  34 |     // Submit feedback
  35 |     const feedbackInput = page.locator('input[placeholder*="experimental"]')
  36 |       .or(page.locator('input[placeholder*="more"]'));
  37 |     await feedbackInput.fill('prefer more loopable progressions');
  38 |     await page.getByRole('button', { name: /send/i }).click();
  39 |     await expect(page.locator('text=Understood')).toBeVisible({ timeout: 15_000 });
  40 | 
  41 |     // Back to progressions
  42 |     await page.getByText('Back to progressions').or(page.getByText('Back')).click();
  43 |     await page.waitForTimeout(500);
  44 | 
  45 |     // Generate round 2 with feedback applied
  46 |     await page.locator('input').first().fill('Continue with feedback applied');
  47 |     await page.getByRole('button', { name: /generate/i }).click();
  48 | 
  49 |     // Should complete without error
  50 |     await page.locator('text=→').first().waitFor({ timeout: 60_000 });
  51 |     await expect(page.locator('text=Error').first()).toBeHidden();
  52 |   });
  53 | });
  54 | 
```