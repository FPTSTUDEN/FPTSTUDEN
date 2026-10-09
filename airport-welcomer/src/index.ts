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

const SVG_PATH = "/readme-immigration-printer.svg";
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
		"Immigration control arrival card being printed by a gate printer: entry granted at Hanoi, Vietnam on 07 Oct 2026 at 18:16. Reason for visit: browsing someone's README.": `Immigration control arrival card being printed by a gate printer: entry granted at ${place} on ${arrival.date} at ${arrival.time}. Reason for visit: browsing someone's README.`,
		"<svg ": `<svg class="${arrival.isDark ? "theme-dark" : "theme-light"}" `,
		"Hanoi, Vietnam": place, "0007 1018": id, "07 OCT 2026": arrival.date,
		"HANOI  HAN  VIETNAM": stampPlace, "07 OCT 2026  18:16": `${arrival.date}  ${arrival.time}`,
		"HAN0710261816": `${arrival.countryCode}${arrival.date.replaceAll(" ", "")}${arrival.time.replace(":", "")}`,
		"18:16": arrival.time,
	};
	return Object.entries(replacements).reduce((result, [from, to]) => result.replaceAll(from, xmlEscape(to)), svg)
		.replace("@media (prefers-color-scheme:dark)", arrival.isDark ? "@media all" : "@media not all");
}

export { formatArrival, renderSvg };

export default {
	async fetch(request, env): Promise<Response> {
		const asset = await env.ASSETS.fetch(new URL(SVG_PATH, request.url));
		if (!asset.ok) return asset;
		return new Response(renderSvg(await asset.text(), request.cf as IncomingRequestCfProperties ?? {} as IncomingRequestCfProperties), {
			headers: { "content-type": "image/svg+xml; charset=utf-8", "cache-control": "no-store" },
		});
	},
} satisfies ExportedHandler<Env>;
