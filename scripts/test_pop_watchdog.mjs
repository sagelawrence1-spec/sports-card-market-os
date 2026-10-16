#!/usr/bin/env node
// Safety checks for the static POP Watchdog and its per-card audit contract.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Script } from 'node:vm';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const base = path.join(root,'alpha-web','public','psa-pop-watchdog');
const html = fs.readFileSync(path.join(base,'index.html'), 'utf8');
const raw = JSON.parse(fs.readFileSync(path.join(base,'populations.json'), 'utf8'));
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1,'Expected one standalone script in POP Watchdog');
new Script(scripts[0][1],{filename:'pop-watchdog-inline.js'});
for(const id of ['cards','auditRows','auditSummary','auditBreakdown','checkedCount','detailAudit','feedStatus']){
 assert.ok(html.includes('id="'+id+'"'),'Missing dashboard audit element: '+id);
}
assert.ok(html.includes('function renderAuditDetail(c)'), 'No detail audit renderer');
assert.ok(html.includes('c.daily_checks='), 'Daily audit file is not synced into the interface');

const expected=new Map([
 ['Charizard','06'],['Ivysaur','02'],['Pikachu','25'],['Onix','95'],
 ['Scyther','123'],['Snorlax','143'],['Dragonite','149'],
]);
assert.ok(Array.isArray(raw.cards),'Missing cards');
assert.equal(raw.cards.length,expected.size,'KFC set must contain all seven cards');
const validStatuses=new Set(['VERIFIED_COUNT','STALE_SOURCE','UNAVAILABLE','AMBIGUOUS']);
const lastRun=raw.last_scan_at?.slice(0,10);
const seen=new Set();
let countToday=0;
for(const c of raw.cards){
 assert.ok(expected.has(c.name),'Unexpected card: '+c.name);
 assert.equal(Number(c.number),Number(expected.get(c.name)),'Incorrect KFC number for '+c.name);
 assert.ok(!seen.has(c.name),'Duplicate card: '+c.name);
 seen.add(c.name);
 assert.ok(Array.isArray(c.history) && c.history.length>0,'Missing history for '+c.name);
 for(const snap of c.history){
   assert.ok(/^20\d{2}-\d{2}(?:-\d{2})?$/.test(snap.date),'Invalid observation date for '+c.name);
   assert.ok(Number.isSafeInteger(snap.psa10)&&snap.psa10>=0,'Invalid count for '+c.name);
 }
 if(lastRun){
   assert.ok(Array.isArray(c.daily_checks),'Missing audit records for '+c.name);
   const matches=c.daily_checks.filter(x=>x.checked_at?.slice(0,10)===lastRun);
   assert.ok(matches.length>0,'Missing latest audit result for '+c.name+' on '+lastRun);
   for(const check of matches){
     assert.ok(validStatuses.has(check.status),'Unknown status for '+c.name);
     if(check.status==='VERIFIED_COUNT')assert.ok(Number.isSafeInteger(check.observed_psa10),'No verified observation for '+c.name);
     if(check.status==='STALE_SOURCE')assert.ok(check.source_as_of,'Stale source must record date for '+c.name);
   }
   countToday++;
 }
}
if(lastRun)assert.equal(countToday,7,'Latest audit must cover seven cards');
console.log('POP Watchdog UI parses and seven-card historical audit contract passes ('+countToday+' latest checks).');
