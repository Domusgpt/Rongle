import { test, expect } from '@playwright/test';

test.describe('Rongle Agent E2E', () => {
  test('Dashboard loads and shows Authentication', async ({ page }) => {
    // 1. Navigate to app
    await page.goto('http://localhost:3000');

    // 2. Check for Auth Gate (since we removed Direct Mode)
    // Expect to see "Sign In" or "Register"
    await expect(page.getByText(/Sign In|Rongle/i)).toBeVisible();
    await expect(page.getByText('HARDWARE AGENTIC OPERATOR')).toBeVisible();
  });

  test('Auth flow (Mocked) leads to Device Manager', async ({ page }) => {
    await page.goto('http://localhost:3000');

    // Mock the API response for login to avoid hitting real backend
    await page.route('**/api/auth/login', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock_token',
          token_type: 'bearer',
          user: { id: 'u1', email: 'test@rongle.io', tier: 'pro' }
        })
      });
    });

    // Mock device list
    await page.route('**/api/devices/', async route => {
        await route.fulfill({
          status: 200,
          body: JSON.stringify([{
              id: 'd1', name: 'Test Device', is_online: true, hardware_type: 'pi'
          }])
        });
    });

    // Perform Login
    await page.fill('input[type="email"]', 'test@rongle.io');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');

    // 3. Verify Dashboard Access
    await expect(page.getByText('Devices (1)')).toBeVisible();
    await expect(page.getByText('Test Device')).toBeVisible();
  });
});
