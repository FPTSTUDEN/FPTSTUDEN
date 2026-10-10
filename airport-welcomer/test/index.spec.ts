import {
	env,
	createExecutionContext,
	waitOnExecutionContext,
	SELF,
} from "cloudflare:test";
import { describe, it, expect } from "vitest";
import worker, { formatArrival, renderLocalizedSvg, renderSvg } from "../src/index";

// For now, you'll need to do something like this to get a correctly-typed
// `Request` to pass to `worker.fetch()`.
const IncomingRequest = Request<unknown, IncomingRequestCfProperties>;

describe("localized arrival SVG", () => {
	it("formats the request location and local time", () => {
		const arrival = formatArrival({ city: "Tokyo", country: "JP", timezone: "Asia/Tokyo" }, new Date("2026-10-09T09:16:00Z"));
		expect(arrival).toMatchObject({ city: "Tokyo", country: "Japan", date: "09 OCT 2026", time: "18:16", isDark: true });
	});

	it("localizes the SVG and randomizes its form number", () => {
		const source = "<svg xmlns=\"http://www.w3.org/2000/svg\"><title>Hanoi, Vietnam 0007 1018 07 OCT 2026  18:16</title><style>@media (prefers-color-scheme:dark){.paper{fill:#18202B}}</style></svg>";
		const first = renderSvg(source, { city: "Paris", country: "FR", timezone: "Europe/Paris" }, new Date("2026-10-09T09:16:00Z"));
		const second = renderSvg(source, { city: "Paris", country: "FR", timezone: "Europe/Paris" }, new Date("2026-10-09T09:16:00Z"));
		expect(first).toContain("Paris, France");
		expect(first).toContain("@media not all");
		expect(first).not.toBe(second);
	});
});

describe("additional localized SVGs", () => {
	it("localizes the speech bubble", () => {
		const source = "<svg><text>Good day, visitor from Hanoi, Vietnam. The local time at your point of origin is 6:16 p.m.</text></svg>";
		const rendered = renderLocalizedSvg(source, "/speech-bubble.svg", { city: "Tokyo", country: "JP", timezone: "Asia/Tokyo" }, new Date("2026-10-09T09:16:00Z"));
		expect(rendered).toContain("Tokyo, Japan");
		expect(rendered).toContain("6:16 PM");
	});

	it("localizes the arrivals board", () => {
		const source = "<svg>Arrivals 09:20 AMSTERDAM</svg>";
		const rendered = renderLocalizedSvg(source, "/arrivals.svg", { city: "Tokyo", country: "JP", timezone: "Asia/Tokyo" }, new Date("2026-10-09T09:16:00Z"));
		expect(rendered).toContain("6:16 PM");
		expect(rendered).toContain("TOKYO");
	});
});

describe("worker", () => {
	it("serves the localized SVG (unit style)", async () => {
		const request = new IncomingRequest("http://example.com/readme-immigration-printer.svg");
		// Create an empty context to pass to `worker.fetch()`.
		const ctx = createExecutionContext();
		const response = await worker.fetch(request, env, ctx);
		// Wait for all `Promise`s passed to `ctx.waitUntil()` to settle before running test assertions
		await waitOnExecutionContext(ctx);
		expect(response.headers.get("content-type")).toContain("image/svg+xml");
		expect(await response.text()).toContain("Unknown city");
	});

	it("serves the localized SVG (integration style)", async () => {
		const response = await SELF.fetch("https://example.com");
		expect(response.headers.get("content-type")).toContain("image/svg+xml");
		expect(await response.text()).toContain("Unknown city");
	});
});
