/**
 * Welcome to Cloudflare Workers! This is your first worker.
 *
 * - Run `npm run dev` in your terminal to start a development server
 * - Open a browser tab at http://localhost:8787/ to see your worker in action
 * - Run `npm run deploy` to publish your worker
 *
 * Bind resources to your worker in `wrangler.jsonc`. After adding bindings, a type definition for the
 * `Env` object can be regenerated with `npm run cf-typegen`.
 *
 * Learn more at https://developers.cloudflare.com/workers/
 */

const DEFAULT_SVG_PATH = "/readme-immigration-printer.svg";
const SVG_PATHS = new Set([DEFAULT_SVG_PATH, "/arrivals.svg", "/speech-bubble.svg"]);
const FALLBACK_TIME_ZONE = "UTC";

function xmlEscape(value: string): string {
	return value.replace(/[&<>"']/g, (character) => ({
		"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;",
	}[character] ?? character));
}

function formatArrival(cf: IncomingRequestCfProperties, now = new Date()) {
	const timeZone = cf.timezone ?? FALLBACK_TIME_ZONE;
	let parts: Record<string, string> = {};
	try {
		for (const part of new Intl.DateTimeFormat("en-GB", {
			timeZone, day: "2-digit", month: "short", year: "numeric",
			hour: "2-digit", minute: "2-digit", hourCycle: "h23",
		}).formatToParts(now)) parts[part.type] = part.value;
	} catch {
		return formatArrival({ ...cf, timezone: FALLBACK_TIME_ZONE }, now);
	}
	const hour = Number(parts.hour ?? "12");
	const countryCode = cf.country ?? "XX";
	let country = countryCode;
	try { country = new Intl.DisplayNames(["en"], { type: "region" }).of(countryCode) ?? countryCode; } catch { /* Unsupported runtime data. */ }
	return {
		city: cf.city ?? "Unknown city", country, countryCode,
		date: `${parts.day} ${(parts.month ?? "").toUpperCase()} ${parts.year}`,
		time: `${parts.hour}:${parts.minute}`, isDark: hour < 6 || hour >= 18,
	};
}

function renderSvg(svg: string, cf: IncomingRequestCfProperties, now = new Date()): string {
	const arrival = formatArrival(cf, now);
	const place = `${arrival.city}, ${arrival.country}`;
	const stampPlace = `${arrival.city.toUpperCase()}  ${arrival.countryCode}  ${arrival.country.toUpperCase()}`;
	const id = crypto.randomUUID().replaceAll("-", "").slice(0, 8).toUpperCase();
	const replacements: Record<string, string> = {
		"Immigration control arrival card being printed by a gate printer: entry granted at Hanoi, Vietnam on 07 Oct 2026 at 18:16. Reason for visit: browsing someone's README.": `Immigration control arrival card being printed by a gate printer: entry granted at ${xmlEscape(place)} on ${xmlEscape(arrival.date)} at ${xmlEscape(arrival.time)}. Reason for visit: browsing someone's README.`,
		"Hanoi, Vietnam": xmlEscape(place), "0007 1018": id, "07 OCT 2026": xmlEscape(arrival.date),
		"HANOI  HAN  VIETNAM": xmlEscape(stampPlace), "07 OCT 2026  18:16": `${xmlEscape(arrival.date)}  ${xmlEscape(arrival.time)}`,
		"HAN0710261816": xmlEscape(`${arrival.countryCode}${arrival.date.replaceAll(" ", "")}${arrival.time.replace(":", "")}`),
		"18:16": xmlEscape(arrival.time),
	};
	let rendered = `<svg class="${arrival.isDark ? "theme-dark" : "theme-light"}" ` + svg.slice(5);
	for (const [from, to] of Object.entries(replacements)) rendered = rendered.replaceAll(from, to);
	return rendered.replace("@media (prefers-color-scheme:dark)", arrival.isDark ? "@media all" : "@media not all");
}

function renderLocalizedSvg(svg: string, path: string, cf: IncomingRequestCfProperties, now = new Date()): string {
	if (path === DEFAULT_SVG_PATH) return renderSvg(svg, cf, now);

	const arrival = formatArrival(cf, now);
	const place = `${arrival.city}, ${arrival.country}`;
	const localTime = new Intl.DateTimeFormat("en-US", {
		timeZone: cf.timezone ?? FALLBACK_TIME_ZONE,
		hour: "numeric", minute: "2-digit", hour12: true,
	}).format(now);
	let rendered = `<svg class="${arrival.isDark ? "theme-dark" : "theme-light"}" ` + svg.slice(5);
	if (path === "/speech-bubble.svg") {
		for (const [from, to] of Object.entries({ "Hanoi, Vietnam": place, "6:16 p.m.": localTime })) {
			rendered = rendered.replaceAll(from, xmlEscape(to));
		}
		return rendered;
	}

	const replaceBoardSlots = (startX: number, value: string, y = "174.4") => {
		[...value].forEach((character, index) => {
			const x = startX + index * 18;
			const pattern = new RegExp(`(<text x="${x.toFixed(1)}" y="${y}">)[^<]*(</text>)`, "g");
			rendered = rendered.replace(pattern, `$1${xmlEscape(character)}$2`);
		});
	};
	const localTime24 = new Intl.DateTimeFormat("en-GB", {
		timeZone: cf.timezone ?? FALLBACK_TIME_ZONE, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
	}).format(now);
	replaceBoardSlots(45.5, localTime24);
	rendered = rendered.replace(/(<text x="45\.5" y="174\.4">)[^<]*(<\/text>)/, `$1${xmlEscape(localTime24)}$2`);
	replaceBoardSlots(172.5, arrival.city.toUpperCase().slice(0, 14));
	return rendered.replace("AMSTERDAM", xmlEscape(arrival.city.toUpperCase()));
}

export { formatArrival, renderSvg, renderLocalizedSvg };

export default {
	async fetch(request, env): Promise<Response> {
		const path = new URL(request.url).pathname;
		const assetPath = SVG_PATHS.has(path) ? path : DEFAULT_SVG_PATH;
		const asset = await env.ASSETS.fetch(new URL(assetPath, request.url));
		if (!asset.ok) return asset;
		return new Response(renderLocalizedSvg(await asset.text(), assetPath, request.cf as IncomingRequestCfProperties ?? {} as IncomingRequestCfProperties), {
			headers: { "content-type": "image/svg+xml; charset=utf-8", "cache-control": "no-store" },
		});
	},
} satisfies ExportedHandler<Env>;
