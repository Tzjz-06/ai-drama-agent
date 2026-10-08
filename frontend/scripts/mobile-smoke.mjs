import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';

// Use the caller's browser runtime; this check never writes to the real account store.
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_URL || 'http://127.0.0.1:8765';
const output = process.env.SMOKE_OUTPUT || '../outputs/mobile-smoke';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.BROWSER_PATH });
const production = {
  title: '雨夜来信', metadata: {}, continuity_issues: [],
  characters: [{ id: 'C001', name: '林默', role: '快递员', appearance: '短发青年', costume: '黑色外套', turnaround_prompt: '角色三视图' }],
  scenes: [{ id: 'S001', name: '雨夜便利店', location: '便利店', time: '夜', lighting: '冷色灯光', layout: '临街玻璃门', environment_prompt: '雨夜便利店空场景' }], props: [],
  shots: [{ id: 'shot_001', scene_id: 'S001', character_ids: ['C001'], prop_ids: [], start_second: 0, duration_seconds: 5, shot_size: '中景', camera_position: '平视', lens: '35mm', camera_motion: '缓推', visual_action: '林默推开玻璃门。', dialogue: '有人吗？', sound_design: '风铃声', first_frame_prompt: '林默站在门外。', video_prompt: '林默推门进入便利店。', last_frame_prompt: '林默停在柜台前。', negative_prompt: '禁止人物变形', confidence: '高', status: 'draft' }],
};
const chapters = [1, 2].map(n => ({ id: `chapter_${n}`, episode_no: n, title: n === 1 ? '第一集 · 来信' : '第二集 · 真相', outline: '林默收到一封来信。', content: '雨夜，林默推门走进便利店。', status: 'completed', is_locked: false, production }));
const project = { id: 'project_test', title: '雨夜来信：一封来自未来的信', product_type: 'drama', genre: '悬疑', style: '二维国漫', description: '快递员收到一封来自未来的信。', aspect_ratio: '9:16', status: 'completed', chapter_count: 2, character_count: 1, scene_count: 1, shot_count: 1, updated_at: new Date().toISOString(), chapters };
try {
  for (const width of [375, 390, 430, 844, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: width === 844 ? 390 : 900 }, serviceWorkers: 'block', reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      let data = {};
      if (path === '/api/runtime') data = { version: 'test', offline_demo: false, environment_model_configured: false };
      else if (path === '/api/auth/login' || path === '/api/auth/me') data = { token: 'test-session', user: { id: 'user_test', username: '测试导演', email: '' } };
      else if (path === '/api/projects') data = { projects: [project] };
      else if (path === '/api/sync') data = { revision: 0, changed: false, project_ids: [] };
      else if (path === '/api/projects/project_test') data = { project };
      else if (path.includes('/chapters/') && route.request().method() === 'PATCH') {
        const chapter = chapters.find(c => path.endsWith(c.id));
        Object.assign(chapter, route.request().postDataJSON()); data = { chapter };
      }
      await route.fulfill({ json: data });
    });
    async function check(name) {
      await page.waitForTimeout(150);
      const result = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, center: document.elementFromPoint(innerWidth / 2, innerHeight / 2)?.className }));
      assert.ok(result.scroll <= result.width + 1, `${width} ${name} overflow: ${JSON.stringify(result)}`);
      assert.ok(!['t-dialog__ctx', 't-drawer'].includes(result.center), `${name} blocked by a closed overlay`);
      assert.deepEqual(errors, [], `${width} ${name} browser errors`);
      if ([390, 1440].includes(width)) await page.screenshot({ path: `${output}/${width}-${name}.png`, fullPage: true });
    }
    await page.goto(base);
    await page.locator('.auth-form').waitFor();
    await check('login');
    assert.equal(await page.getByText(/微信扫码|短信验证码|手机号|获取验证码/).count(), 0);
    await page.getByRole('button', { name: '注册', exact: true }).click();
    await check('register');
    assert.equal(await page.getByText(/微信扫码|短信验证码|手机号|获取验证码/).count(), 0);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await page.locator('input[name=username]').fill('测试导演');
    await page.locator('input[name=password]').fill('test-password');
    await page.getByRole('button', { name: '进入创作台' }).click();
    await page.locator('.project-tile').first().waitFor();
    await check('projects');
    assert.equal(await page.locator('.mobile-tabbar').isVisible(), width <= 900);
    assert.equal(await page.locator('.studio-sidebar').isVisible(), width > 900);
    await page.locator('.project-tile').first().click();
    await page.locator('.script-input').waitFor();
    if (width <= 900) {
      await page.locator('#mobile-chapter').selectOption('chapter_2');
      await page.locator('.script-input').fill('手机端编辑后的正文。');
      await page.getByRole('button', { name: '保存章节', exact: true }).click();
      assert.equal(chapters[1].content, '手机端编辑后的正文。');
      await page.locator('#mobile-chapter').selectOption('chapter_1');
    }
    await check('script');
    const nav = page.locator(width <= 900 ? '.mobile-tabbar' : '.main-nav');
    await nav.locator('button').nth(2).click();
    await page.locator('.asset-card').first().waitFor();
    await check('assets');
    await page.getByTitle('编辑资产', { exact: true }).first().click();
    await page.locator('.t-dialog:visible').waitFor();
    await check('asset-dialog');
    await page.keyboard.press('Escape');
    await nav.locator('button').nth(3).click();
    await page.locator('.shot-list').waitFor();
    await check('storyboard');
    if (width <= 900) {
      await page.getByRole('button', { name: '账户与设置', exact: true }).click();
      await check('account');
      await page.locator('.mobile-account-panel').getByRole('button', { name: '模型与环境' }).click();
    } else await page.locator('.main-nav').getByRole('button', { name: '模型与环境' }).click();
    await page.locator('.t-drawer__content-wrapper:visible').waitFor();
    await check('settings');
    console.log(`${width}px: password-only login/register, projects, script, assets, storyboard, dialogs OK`);
    await page.close();
  }
} finally { await browser.close(); }
