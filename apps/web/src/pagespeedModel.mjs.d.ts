export const CATEGORY_IDS: string[];
export function normalizeClientUrl(value: string): string;
export function auditState(audit: Record<string, any>): string;
export function flattenAudits(result: Record<string, any>): Array<Record<string, any>>;
export function latestByStrategy(results: Array<Record<string, any>>): { mobile: Record<string, any> | null; desktop: Record<string, any> | null };
export function deviceOutcome(results: Record<string, Record<string, any>>): "idle" | "success" | "partial" | "error";
