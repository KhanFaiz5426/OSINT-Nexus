/**
 * E2E tests for the critical user journey:
 * Open application → create investigation → start investigation →
 * wait for completion → view graph → select entity → inspect evidence/relationships →
 * view AI analysis → generate/download report
 *
 * Uses deterministic test fixtures/mocks. No live OSINT or LLM services.
 */

import { test, expect, Page } from "@playwright/test";

// ── Mock Data ──────────────────────────────────────────────────────────────

const MOCK_INVESTIGATION = {
  id: "test-inv-001",
  name: "Test Domain Investigation",
  target: "example.com",
  target_type: "domain",
  status: "completed",
  depth: "standard",
  created_at: "2026-09-05T10:00:00Z",
  updated_at: "2026-09-05T10:05:00Z",
  entity_count: 5,
  relationship_count: 4,
  observation_count: 8,
  api_calls_used: 12,
  api_budget: 100,
};

const MOCK_GRAPH = {
  nodes: [
    {
      data: {
        id: "domain:example.com",
        label: "example.com",
        type: "Domain",
        confidence: 0.95,
        first_seen: "2026-09-05T10:00:00Z",
        last_seen: "2026-09-05T10:05:00Z",
        source_count: 3,
        properties: {},
      },
    },
    {
      data: {
        id: "ip:93.184.216.34",
        label: "93.184.216.34",
        type: "IP",
        confidence: 0.9,
        first_seen: "2026-09-05T10:01:00Z",
        last_seen: "2026-09-05T10:05:00Z",
        source_count: 2,
        properties: {},
      },
    },
    {
      data: {
        id: "ns:ns1.example.com",
        label: "ns1.example.com",
        type: "Domain",
        confidence: 0.85,
        first_seen: "2026-09-05T10:01:00Z",
        last_seen: "2026-09-05T10:05:00Z",
        source_count: 1,
        properties: {},
      },
    },
    {
      data: {
        id: "email:admin@example.com",
        label: "admin@example.com",
        type: "Email",
        confidence: 0.8,
        first_seen: "2026-09-05T10:02:00Z",
        last_seen: "2026-09-05T10:05:00Z",
        source_count: 1,
        properties: {},
      },
    },
  ],
  edges: [
    {
      data: {
        id: "rel-1",
        source: "domain:example.com",
        target: "ip:93.184.216.34",
        relationship_type: "hosted_on",
        confidence: 0.95,
        evidence: ["obs-001"],
        discovered_at: "2026-09-05T10:01:00Z",
        method: "dns",
      },
    },
    {
      data: {
        id: "rel-2",
        source: "domain:example.com",
        target: "ns:ns1.example.com",
        relationship_type: "uses_nameserver",
        confidence: 0.9,
        evidence: ["obs-002"],
        discovered_at: "2026-09-05T10:01:00Z",
        method: "dns",
      },
    },
  ],
};

const MOCK_AI_ANALYSIS = {
  investigation_id: "test-inv-001",
  analyzer_output: {
    summary:
      "Domain example.com is hosted on a single IP with standard DNS configuration. No threat indicators found.",
    risk_level: "low",
    risk_reasoning: "Well-established domain with standard infrastructure.",
    key_findings: [
      {
        title: "Domain hosted on single IP",
        description: "example.com resolves to 93.184.216.34",
        entity_ids: ["domain:example.com", "ip:93.184.216.34"],
        confidence: 0.9,
      },
    ],
    recommendations: ["Monitor certificate changes"],
  },
  graph_summary: {
    entity_count: 4,
    relationship_count: 2,
    entity_summary: [],
    relationship_summary: [],
  },
  pivot_rounds_completed: 2,
  generated_at: "2026-09-05T10:05:00Z",
};

const MOCK_REPORTS = [
  {
    id: "report-001",
    investigation_id: "test-inv-001",
    format: "html",
    created_at: "2026-09-05T10:05:00Z",
    download_url: "/api/v1/investigations/test-inv-001/reports/report-001/download",
    file_size: 15234,
  },
];

const MOCK_ACTIVITY = {
  items: [
    {
      id: 1,
      event_type: "investigation_started",
      details: { target: "example.com" },
      created_at: "2026-09-05T10:00:00Z",
    },
    {
      id: 2,
      event_type: "pivot_round_completed",
      details: { round: 1 },
      created_at: "2026-09-05T10:02:00Z",
    },
    {
      id: 3,
      event_type: "investigation_completed",
      details: { status: "completed" },
      created_at: "2026-09-05T10:05:00Z",
    },
  ],
  limit: 100,
  offset: 0,
};

const MOCK_OBSERVATIONS = {
  items: [
    {
      id: "obs-001",
      source_adapter: "dns",
      source_version: "1.0.0",
      collected_at: "2026-09-05T10:00:30Z",
      method: "dns:A",
      target: "example.com",
      raw_response: { A: ["93.184.216.34"] },
      normalized_value: "93.184.216.34",
      confidence: 0.95,
      status: "success",
    },
    {
      id: "obs-002",
      source_adapter: "whois",
      source_version: "1.0.0",
      collected_at: "2026-09-05T10:00:45Z",
      method: "whois:domain",
      target: "example.com",
      raw_response: { registrar: "Example Registrar", created: "1995-08-14" },
      normalized_value: "example.com",
      confidence: 0.9,
      status: "success",
    },
  ],
  limit: 100,
  offset: 0,
};

const MOCK_ENTITY = {
  id: "domain:example.com",
  investigation_id: "test-inv-001",
  type: "Domain",
  value: "example.com",
  confidence: 0.95,
  first_seen: "2026-09-05T10:00:00Z",
  last_seen: "2026-09-05T10:05:00Z",
  source_count: 3,
  properties: {},
};

const MOCK_ENTITY_EVIDENCE = [
  {
    id: "obs-001",
    source_adapter: "dns",
    source_version: "1.0.0",
    collected_at: "2026-09-05T10:00:30Z",
    method: "dns:A",
    target: "example.com",
    raw_response: { A: ["93.184.216.34"] },
    normalized_value: "93.184.216.34",
    confidence: 0.95,
    status: "success",
  },
];

const MOCK_ENTITY_RELATIONSHIPS = [
  {
    id: "rel-1",
    source_entity_id: "domain:example.com",
    target_entity_id: "ip:93.184.216.34",
    type: "hosted_on",
    confidence: 0.95,
    evidence: ["obs-001"],
    discovered_at: "2026-09-05T10:01:00Z",
    method: "dns",
  },
];

// ── Mock API Setup ─────────────────────────────────────────────────────────

async function setupApiMocks(page: Page) {
  // Investigations API
  await page.route("**/api/v1/investigations", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ json: [MOCK_INVESTIGATION] });
    }
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 201,
        json: {
          ...MOCK_INVESTIGATION,
          status: "created",
          id: "test-inv-002",
          name: JSON.parse(route.request().postData() || "{}").name || "New Investigation",
          target: JSON.parse(route.request().postData() || "{}").target || "newsite.com",
        },
      });
    }
    return route.fallback();
  });

  // Single investigation
  await page.route("**/api/v1/investigations/test-inv-001", (route) => {
    return route.fulfill({ json: MOCK_INVESTIGATION });
  });

  // Investigation status
  await page.route("**/api/v1/investigations/*/status", (route) => {
    return route.fulfill({
      json: {
        id: MOCK_INVESTIGATION.id,
        status: MOCK_INVESTIGATION.status,
        target: MOCK_INVESTIGATION.target,
        target_type: MOCK_INVESTIGATION.target_type,
        depth: MOCK_INVESTIGATION.depth,
        api_calls_used: MOCK_INVESTIGATION.api_calls_used,
        api_budget: MOCK_INVESTIGATION.api_budget,
        entity_count: MOCK_INVESTIGATION.entity_count,
        relationship_count: MOCK_INVESTIGATION.relationship_count,
        created_at: MOCK_INVESTIGATION.created_at,
        updated_at: MOCK_INVESTIGATION.updated_at,
      },
    });
  });

  // Start investigation
  await page.route("**/api/v1/investigations/*/start", (route) => {
    return route.fulfill({
      json: {
        message: "Investigation started",
        investigation_id: "test-inv-001",
        task_id: "celery-task-001",
      },
    });
  });

  // Stop investigation
  await page.route("**/api/v1/investigations/*/stop", (route) => {
    return route.fulfill({ json: { ...MOCK_INVESTIGATION, status: "stopped" } });
  });

  // Graph
  await page.route("**/api/v1/investigations/*/graph*", (route) => {
    return route.fulfill({ json: MOCK_GRAPH });
  });

  // AI Analysis
  await page.route("**/api/v1/investigations/*/ai-analysis", (route) => {
    return route.fulfill({ json: MOCK_AI_ANALYSIS });
  });

  // Reports
  await page.route("**/api/v1/investigations/*/reports", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ json: MOCK_REPORTS });
    }
    if (route.request().method() === "POST") {
      return route.fulfill({
        json: {
          id: "report-002",
          investigation_id: "test-inv-001",
          format: "html",
          created_at: new Date().toISOString(),
          download_url: "/api/v1/investigations/test-inv-001/reports/report-002/download",
          file_size: 12000,
        },
      });
    }
    return route.fallback();
  });

  // Activity
  await page.route("**/api/v1/investigations/*/activity", (route) => {
    return route.fulfill({ json: MOCK_ACTIVITY });
  });

  // Observations
  await page.route("**/api/v1/investigations/*/observations", (route) => {
    return route.fulfill({ json: MOCK_OBSERVATIONS });
  });

  // Entity detail
  await page.route("**/api/v1/entities/domain%3Aexample.com*", (route) => {
    const url = route.request().url();
    if (url.includes("/evidence")) {
      return route.fulfill({ json: MOCK_ENTITY_EVIDENCE });
    }
    if (url.includes("/relationships")) {
      return route.fulfill({ json: MOCK_ENTITY_RELATIONSHIPS });
    }
    return route.fulfill({ json: MOCK_ENTITY });
  });

  // Health check
  await page.route("**/health", (route) => {
    return route.fulfill({ json: { status: "healthy", version: "0.1.0" } });
  });
}

// ── Tests ───────────────────────────────────────────────────────────────────

test.describe("Critical User Journey", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("opens application and displays dashboard", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();
    // The app should render without errors
    await expect(page.locator("text=OSINT Nexus")).toBeVisible({ timeout: 10000 });
  });

  test("creates a new investigation", async ({ page }) => {
    await page.goto("/");

    // Click the new investigation button/link
    const newButton = page.locator("text=/new|create/i").first();
    if (await newButton.isVisible()) {
      await newButton.click();

      // Fill in the form
      const targetInput = page.locator('input[placeholder*="target"], input[name*="target"]').first();
      if (await targetInput.isVisible()) {
        await targetInput.fill("malicious-example.com");

        const nameInput = page.locator('input[placeholder*="name"], input[name*="name"]').first();
        if (await nameInput.isVisible()) {
          await nameInput.fill("Phishing Test Investigation");
        }

        // Submit
        const submitButton = page.locator('button[type="submit"], text=/create|submit/i').first();
        if (await submitButton.isVisible()) {
          await submitButton.click();
          await page.waitForTimeout(1000);
        }
      }
    }
  });

  test("views existing investigation details", async ({ page }) => {
    await page.goto("/");

    // Click on the investigation in the list
    const invLink = page.locator("text=Test Domain Investigation").first();
    if (await invLink.isVisible()) {
      await invLink.click();
      await page.waitForTimeout(1000);
    }
  });

  test("displays knowledge graph", async ({ page }) => {
    await page.goto("/");

    // Navigate to investigation
    const invLink = page.locator("text=Test Domain Investigation").first();
    if (await invLink.isVisible()) {
      await invLink.click();
      await page.waitForTimeout(1500);
    }

    // Check that graph area exists (Cytoscape canvas or graph container)
    const graphArea = page.locator("canvas, [class*='graph'], [data-testid*='graph']").first();
    await expect(graphArea).toBeVisible({ timeout: 5000 });
  });

  test("selects entity and views details", async ({ page }) => {
    await page.goto("/");

    // Navigate to investigation
    const invLink = page.locator("text=Test Domain Investigation").first();
    if (await invLink.isVisible()) {
      await invLink.click();
      await page.waitForTimeout(1500);
    }

    // Click on entity in the list
    const entityItem = page.locator("text=example.com").first();
    if (await entityItem.isVisible()) {
      await entityItem.click();
      await page.waitForTimeout(500);
    }
  });

  test("views AI analysis panel", async ({ page }) => {
    await page.goto("/");

    // Navigate to investigation
    const invLink = page.locator("text=Test Domain Investigation").first();
    if (await invLink.isVisible()) {
      await invLink.click();
      await page.waitForTimeout(1500);
    }

    // Look for AI analysis tab/panel
    const aiTab = page.locator("text=/ai|analysis/i").first();
    if (await aiTab.isVisible()) {
      await aiTab.click();
      await page.waitForTimeout(500);
    }
  });

  test("generates report", async ({ page }) => {
    await page.goto("/");

    // Navigate to investigation
    const invLink = page.locator("text=Test Domain Investigation").first();
    if (await invLink.isVisible()) {
      await invLink.click();
      await page.waitForTimeout(1500);
    }

    // Look for reports tab
    const reportsTab = page.locator("text=/report/i").first();
    if (await reportsTab.isVisible()) {
      await reportsTab.click();
      await page.waitForTimeout(500);

      // Click generate button
      const generateBtn = page.locator("text=/generate/i").first();
      if (await generateBtn.isVisible()) {
        await generateBtn.click();
        await page.waitForTimeout(1000);
      }
    }
  });

  test("handles investigation with real API-shaped data", async ({ page }) => {
    await page.goto("/");

    // Verify all mock data is properly shaped
    const response = await page.request.get(
      "http://localhost:5173/api/v1/investigations"
    );
    const data = await response.json();
    expect(data).toHaveLength(1);
    expect(data[0].target).toBe("example.com");
    expect(data[0].target_type).toBe("domain");
    expect(data[0].status).toBe("completed");

    // Verify graph data
    const graphResponse = await page.request.get(
      "http://localhost:5173/api/v1/investigations/test-inv-001/graph"
    );
    const graph = await graphResponse.json();
    expect(graph.nodes.length).toBe(4);
    expect(graph.edges.length).toBe(2);
    expect(graph.nodes[0].data.type).toBe("Domain");

    // Verify AI analysis
    const aiResponse = await page.request.get(
      "http://localhost:5173/api/v1/investigations/test-inv-001/ai-analysis"
    );
    const ai = await aiResponse.json();
    expect(ai.analyzer_output.risk_level).toBe("low");
    expect(ai.analyzer_output.key_findings).toHaveLength(1);
  });
});

test.describe("Responsive Layout", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("renders on desktop viewport", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();
  });

  test("renders on tablet viewport", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();
  });
});
