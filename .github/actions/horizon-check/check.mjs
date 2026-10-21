// Checks the horizon/ directory of a repository: the documentation docs.stratastax.dev includes
// (see https://docs.stratastax.dev/technical/contributing-docs/). The manifest rules are those of
// stratastax-docs' scripts/horizon.mjs. Usage: node check.mjs <repository root>
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, posix } from 'node:path';
import { parse } from 'yaml';

const root = process.argv[2] ?? '.';
const groups = ['services', 'contract', 'backend-libraries', 'frontend', 'build-ops'];
const errors = [];
const error = (message) => errors.push(message);

const manifestFile = join(root, 'horizon/horizon.yaml');
if (!existsSync(manifestFile)) {
    console.log('No horizon/horizon.yaml: nothing to check.');
    process.exit(0);
}

let manifest = {};
try {
    manifest = parse(readFileSync(manifestFile, 'utf8')) ?? {};
} catch (e) {
    error(`horizon/horizon.yaml: invalid YAML: ${e.message}`);
}
if (!/^[a-z][a-z0-9-]*$/.test(manifest.id ?? '')) error('horizon.yaml: id must be a lowercase slug');
if (!manifest.title) error('horizon.yaml: title is required');
if (!manifest.summary) error('horizon.yaml: summary is required');
if (!groups.includes(manifest.group)) error(`horizon.yaml: group must be one of ${groups.join(', ')}`);
if (manifest.order !== undefined && typeof manifest.order !== 'number') error('horizon.yaml: order must be a number');

const pages = readdirSync(join(root, 'horizon')).filter((f) => /\.mdx?$/.test(f)).map((f) => `horizon/${f}`);
if (!pages.some((page) => /^horizon\/index\.mdx?$/.test(page))) error('horizon/index.md is missing');
for (const page of manifest.pages ?? []) {
    if (!page.file || !/^[a-z][a-z0-9-]*$/.test(page.slug ?? '')) error(`horizon.yaml: pages: ${page.file ?? '?'} needs a file and a slug`);
    else if (!existsSync(join(root, page.file))) error(`horizon.yaml: pages: ${page.file} does not exist`);
    else pages.push(posix.normalize(page.file));
}

for (const page of pages) {
    const text = readFileSync(join(root, page), 'utf8');
    const frontmatter = /^---\n([\s\S]*?)\n---\n/.exec(text);
    if (frontmatter) {
        try {
            parse(frontmatter[1]);
        } catch (e) {
            error(`${page}: invalid frontmatter: ${e.message}`);
        }
    }
    let fenced = false;
    text.split('\n').forEach((line, i) => {
        if (/^\s*(```|~~~)/.test(line)) fenced = !fenced;
        if (fenced) return;
        // Inline code is left alone: split on backticks and look at the parts outside them.
        const prose = line.split('`').filter((_, part) => part % 2 === 0).join(' ');
        for (const [, target] of prose.matchAll(/!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) {
            if (/^([a-z]+:|#|\/)/i.test(target)) continue;
            const path = posix.normalize(posix.join(posix.dirname(page), decodeURI(target.split('#')[0])));
            if (!existsSync(join(root, path))) error(`${page}:${i + 1}: link to ${target} does not resolve (${path})`);
        }
    });
}

if (errors.length > 0) {
    for (const message of errors) console.log(`::error::${message}`);
    process.exit(1);
}
console.log(`horizon/: ${manifest.id}, ${pages.length} page(s), every relative link resolves.`);
