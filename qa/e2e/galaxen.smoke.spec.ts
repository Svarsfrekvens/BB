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
  // 1. Appen måste starta (menyn fylls) – fångar initBB-buggen
  await expect(page.getByText("Underlag", { exact: false }).first()).toBeVisible({ timeout: 15000 });
  await expect(page.locator("body")).not.toContainText("Vintergatan");

  await page.getByText("Underlag", { exact: false }).first().click();
  const [fc1] = await Promise.all([page.waitForEvent("filechooser"), page.getByRole("button", { name: /^Välj fil$/ }).first().click()]);
  await fc1.setFiles(path.join(fixtures, "Galaxen_sekoia.xlsx"));
  await page.getByRole("button", { name: /Godkänn och läs in/ }).click();
  await expect(page.locator("body")).toContainText("2541 insatser");
  await expect(page.locator("body")).toContainText("578,8 h");

  const [fc2] = await Promise.all([page.waitForEvent("filechooser"), page.getByRole("button", { name: /^Välj fil$/ }).first().click()]);
  await fc2.setFiles(path.join(fixtures, "Schema_galaxen.xlsx"));
  await page.getByRole("button", { name: /Godkänn/ }).first().click();
  await expect(page.locator("body")).toContainText("832");

  // 2. Skapa balans (motorn om den svarar, annars reservläge i appen)
  await page.getByRole("button", { name: /^Skapa bemanningsbalans/ }).first().click();
  const skapa = page.locator("main").getByRole("button", { name: /^Skapa (om )?bemanningsbalans$/ }).last();
  await expect(skapa).toBeEnabled({ timeout: 20_000 });
  await skapa.click();
  await expect(page.locator("main")).toContainText(/Förslaget|Reservläge|schematimmar/, { timeout: 300_000 });

  // 3. Före & efter: kundbehovet oförändrat (samma tal Före och Efter)
  const meny = page.locator("aside");
  const oppna = async (grupp: RegExp, post: RegExp) => {
    const rad = meny.getByRole("button", { name: post }).first();
    if (!(await rad.isVisible().catch(() => false))) {
      await meny.getByRole("button", { name: grupp }).first().click();
    }
    await expect(rad).toBeVisible({ timeout: 300_000 });
    await rad.click();
  };
  await oppna(/^Följ upp/, /^Före & efter/);
  const fe = await page.locator("main").innerText();
  expect(fe).toMatch(/Kundnära tid/);
  const efterH = fe.match(/Planerade personaltimmar\s+832,0 h\s+([\d, ]+)h/)?.[1]?.trim();
  expect(efterH).toBeTruthy();
  const kundbehov = [...fe.matchAll(/Kundernas behov\s+([\d, ]+)h\s+([\d, ]+)h/g)][0];
  expect(kundbehov?.[1]?.trim()).toBe(kundbehov?.[2]?.trim());

  // 4. Samma schematid EFTER i Bemanning
  await oppna(/^Planera/, /^Bemanning/);
  await expect(page.locator("main")).toContainText(`${efterH} h`);

  expect(fel).toEqual([]);
});

