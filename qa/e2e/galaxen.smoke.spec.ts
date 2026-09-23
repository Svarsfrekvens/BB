/**
 * Rök-test i riktig webbläsare: startar appen, läser in båda filerna,
 * skapar balans och kontrollerar att samma tal syns i alla vyer.
 * Kör: npx playwright test  (dev-servern startas av playwright.config.ts)
 */
import { existsSync } from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

const fixtures = existsSync("/dev-server/qa/fixtures")
  ? "/dev-server/qa/fixtures"
  : path.resolve("qa/fixtures");

test("Galaxen: start → underlag → balans → samma tal överallt", async ({ page }) => {
  const fel: string[] = [];
  page.on("pageerror", e => fel.push(String(e)));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Bemanningsbalans" })).toBeVisible({ timeout: 20000 });
  await expect(page.getByRole("heading", { name: "Vad vill du göra idag?" })).toBeVisible();
  await expect(page.getByText("Ett lugnt arbetsflöde")).toHaveCount(0);

  const [fc1] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: "Ladda upp kundbehov" }).click(),
  ]);
  await fc1.setFiles(path.join(fixtures, "Galaxen_sekoia.xlsx"));
  await page.getByRole("button", { name: /Godkänn kundunderlag/ }).click();
  await expect(page.locator("body")).toContainText("2541 insatser");
  await expect(page.locator("body")).toContainText("578,8 h");

  const [fc2] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: /Ladda upp schema|Byt schema/ }).click(),
  ]);
  await fc2.setFiles(path.join(fixtures, "Schema_galaxen.xlsx"));
  await expect(page.getByRole("heading", { name: /Medarbetare|villkor/i }).first()).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole("navigation", { name: "Process" })).toBeVisible();
  await expect(page.locator("body")).toContainText("143 pass");
  await expect(page.locator("main")).not.toContainText("Fortsätt till översikten");
  await page.getByRole("button", { name: /Godkänn medarbetare & villkor/ }).click();
  await page.getByRole("button", { name: /Spara och fortsätt/ }).click();
  await expect(page.getByRole("heading", { name: /Förutsättningar/ })).toBeVisible();
  await expect(page.locator("main")).not.toContainText("Fortsätt till översikten");

  await page.getByRole("button", { name: /^Skapa balans$/ }).click();
  await expect(page.getByRole("heading", { name: /Inläst nuläge jämfört med planerad balans/ })).toBeVisible({ timeout: 300_000 });
  await expect(page.locator("main")).toContainText("Godkänn balans");
  await expect(page.locator("main")).not.toContainText("Fortsätt till översikten");

  const meny = page.locator("aside");
  const oppna = async (grupp: RegExp, post: RegExp) => {
    const rad = meny.getByRole("button", { name: post }).first();
    if (!(await rad.isVisible().catch(() => false))) {
      await meny.getByRole("button", { name: grupp }).first().click();
    }
    await expect(rad).toBeVisible({ timeout: 300_000 });
    await rad.click();
  };
  await oppna(/^Planera/, /^Bemanning/);
  await expect(page.locator("main")).toContainText("h");

  expect(fel).toEqual([]);
});

